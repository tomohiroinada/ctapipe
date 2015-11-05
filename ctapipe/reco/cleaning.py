"""
Image Cleaning Algorithms (identification of noisy pixels)
"""

__all__ = ['tailcuts_clean']


def tailcuts_clean(geom, image, pedvars, picture_thresh=4.25,
                   boundary_thresh=2.25):
    """Clean an image by selection pixels that pass a two-threshold
    tail-cuts procedure.  The picture and boundary thresholds are
    defined with respect to the pedestal dispersion. All pixels that
    have a signal higher than the picture threshold will be retained,
    along with all those above the boundary threshold that are
    neighbors of a picture pixel.

    Parameters
    ----------
    geom: `ctapipe.io.CameraGeometry`
        Camera geometry information
    image: array
        pedestal-subtracted, flat-fielded pixel values
    pedvars: array or scalar
        pedestal dispersion of all pixels, or any other
        multiplicative factor that one wants to use to normalize the
        thresholds (e.g. if your image is already in PE units, this could
        simply be set to 1, and the thresholds defined in PE)
    picture_thresh: float
        high threshold as multiple of the pedvar
    boundary_thresh: float
        low-threshold as mutiple of pedvar (+ nearest neighbor)

    Returns
    -------

    A boolean mask of *clean* pixels.  To get a zero-suppressed image and pixel
    list, use `image[mask], geom.pix_id[mask]`, or to keep the same
    image size and just set unclean pixels to 0 or similar, use
    `image[mask] = 0`

    """

    clean_mask = image >= picture_thresh * pedvars  # starts as picture pixels

    # good boundary pixels are those that have any picture pixel as a
    # neighbor
    boundary_mask = image >= boundary_thresh * pedvars
    boundary_ids = [pix_id for pix_id in geom.pix_id[boundary_mask]
                    if clean_mask[geom.neighbors[pix_id]].any()]

    clean_mask[boundary_ids] = True
    return clean_mask