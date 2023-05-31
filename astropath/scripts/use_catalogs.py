#!/usr/bin/env python
"""
This script runs PATH on a input localization using public catalog data
"""
from IPython import embed

def parser(options=None):
    import argparse
    # Parse
    parser = argparse.ArgumentParser(description='Script to run PATH on a localization')
    parser.add_argument("coord", type=str, help="Central coordinates of the localizatoin, e.g. J081240.7+320809 or 122.223,-23.2322 or 07:45:00.47,34:17:31.1")
    parser.add_argument("lparam", type=str, help="Localization parameters, e.g. 0.5,0.3,45 for ellipse which give semi-major and semi-minor axes and PA (in deg; E from N)")
    parser.add_argument("--ltype", type=str, default='ellipse', help="Localization type [ellipse] FUTURE: wcs, healpix")
    parser.add_argument("-U", "--PU", type=float, default=0., help="Prior on unseen galaxies")
    parser.add_argument("-s", "--survey", type=str, default='Pan-STARRS',
                        help="Public survey to use for the analysis")
    parser.add_argument("--ssize", type=float, default=5., help='Size of the survey in arcmin')
    parser.add_argument("--debug", default=False, action="store_true", help="debug?")
    parser.add_argument("-o", "--outfile", type=str, help="Name of the output file.  Should end in .csv")

    if options is None:
        pargs = parser.parse_args()
    else:
        pargs = parser.parse_args(options)
    return pargs


def main(pargs):
    """ Run
    """
    import numpy as np

    import seaborn as sns
    from matplotlib import pyplot as plt

    from astropy import units

    from frb.surveys import survey_utils

    from astropath import path
    from astropath.scripts.utils import coord_arg_to_coord
    from astropath.utils import radec_to_coord

    scale = 0.5

    if pargs.ltype == 'ellipse':
        a, b, pa = [float(ip) for ip in pargs.lparam.split(',')]
        eellipse = {'a': a, 'b': b, 'theta': pa}

    # Load up the survey
    coord = radec_to_coord(coord_arg_to_coord(pargs.coord))
    survey = survey_utils.load_survey_by_name(
        pargs.survey, coord, pargs.ssize*units.arcmin)

    # Grab the catalog
    catalog = survey.get_catalog(query_fields=['rPSFLikelihood'])

    # Clean up the catalog
    if pargs.survey == 'Pan-STARRS':
        cut_size = catalog['rKronRad'] > 0.
        cut_mag = catalog['Pan-STARRS_r'] > 14. # Reconsider this
        cut_point = np.log10(np.abs(catalog['rPSFLikelihood'])) < (-2)
        keep = cut_size & cut_mag & cut_point
        size_key, mag_key = 'rKronRad', 'Pan-STARRS_r'
    else:
        raise IOError(f"Not ready for this survey: {pargs.survey}")


    catalog = catalog[keep]

    if pargs.debug:
        if pargs.survey == 'Pan-STARRS':
            sns.histplot(x=catalog['Pan-STARRS_r'])#, bins=20)
            plt.show()
            sns.histplot(x=catalog['rKronRad'])#, bins=20)
            plt.show()
            sns.histplot(x=catalog['rPSFLikelihood'])#, bins=20)
            plt.show()
            embed(header='lowdm_bb: Need to set boxsize')

    # Set boxsize accoring to the largest galaxy (arcsec)
    box_hwidth = max(30., 10.*np.max(catalog[size_key]))

    # Turn into a cndidate table
    Path = path.PATH()

   # Set up localization
    Path.init_localization('eellipse', 
                           center_coord=coord, 
                           eellipse=eellipse)
    # Coords
    Path.init_candidates(catalog['ra'],
                         catalog['dec'],
                         catalog[size_key],
                         mag=catalog[mag_key])

    # Candidate prior
    Path.init_cand_prior('inverse', P_U=pargs.PU)

    # Offset prior
    Path.init_theta_prior('exp', 6., scale)

    # Priors
    p_O = Path.calc_priors()

    # Posterior
    P_Ox, P_Ux = Path.calc_posteriors('local', box_hwidth=box_hwidth, 
        max_radius=box_hwidth)

    # Print
    Path.candidates.sort_values(by='P_Ox', ascending=False, inplace=True)
    print(Path.candidates[['ra', 'dec', 'ang_size', 'mag', 'P_O', 'P_Ox']])
    print(f"P_Ux = {Path.candidates['P_Ux'][0]}")

    # Save?
    if pargs.outfile is not None:
        Path.candidates.to_csv(pargs.outfile, index=False)
        print(f"Wrote: {pargs.outfile}")

    # Return
    return Path

# Test
# astropath_catalog 128.6800541558221,66.01075020181487 11.,11.,0. -U 0.2 --survey Pan-STARRS -o tst.csv