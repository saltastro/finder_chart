#!/opt/local/bin/python

import cStringIO
import os
import sys
import xml
import base64
import urllib2
import xml.dom.minidom
import pyfits
import ephem
import numpy as np
import aplpy


# grab MOS xml definition from WM given account and barcode
def get_slitmask_xml(username, password, barcode):
    """
    Return the slit mask XML as a DOM document.
    """
    encoded_username = base64.encodestring(username).strip()
    encoded_password = base64.encodestring(password).strip()

    mask_url = 'https://www.salt.ac.za/wm/downloads/SlitmaskXml.php'

    # We pass the parameters in a GET request.
    url = mask_url + '?username=%s&password=%s&Barcode=%s' % (encoded_username,
                                                              encoded_password,
                                                              barcode)
    response = urllib2.urlopen(url)
    dom = xml.dom.minidom.parse(response)

    # Handle the case that the request wasn't successful.
    if dom.documentElement.tagName == 'Invalid':
        raise Exception('You are not allowed to view the slit mask XML.')

    return dom


# grab 10' x 10' image from STScI server and pull it into pyfits
def get_dss(imserver, ra, dec):
    url = "http://archive.stsci.edu/cgi-bin/dss_search?v=%s&r=%f&d=%f&e=J2000&h=10.0&w=10.0&f=fits&c=none" % (imserver, ra, dec)
    fitsData = cStringIO.StringIO()
    data = urllib2.urlopen(url).read()
    fitsData.write(data)
    fitsData.seek(0)
    return pyfits.open(fitsData)


# grab uploaded base64-encoded FITS
def get_fits(b64str):
    fitsData = cStringIO.StringIO()
    fitsData.write(base64.b64decode(b64str))
    fitsData.seek(0)
    return pyfits.open(fitsData)


# draw a line centered at ra,dec of a given length at a given angle
# theta,ra,dec => deg; length => arcmin
def draw_line(plot, theta, length, ra, dec, color='b', linewidth=1, alpha=0.7):
    theta = theta * np.pi / 180.0
    length = length / 2.0
    dx = np.sin(theta) * length / (np.cos(dec * np.pi / 180.0) * 60.0)
    dy = np.cos(theta) * length / 60.0
    coords = np.array([[ra + dx, ra - dx], [dec + dy, dec - dy]])
    plot.show_lines([coords], color=color, linewidth=linewidth, alpha=alpha)
    return plot


# draw a box centered at ra,dec of a given length and width at a given angle
# theta,ra,dec => deg; width, height => arcmin
def draw_box(plot, theta, width, length, ra, dec,
             color='b', linewidth=1, alpha=0.7):
    theta = theta * np.pi / 180.0
    length = length / 2.0
    width = width / 2.0
    # position of line centers
    ra_l = ra + np.cos(theta) * width / (np.cos(dec * np.pi / 180.0) * 60.0)
    ra_r = ra - np.cos(theta) * width / (np.cos(dec * np.pi / 180.0) * 60.0)
    dec_l = dec - np.sin(theta) * width / 60.0
    dec_r = dec + np.sin(theta) * width / 60.0

    dx = np.sin(theta) * length / (np.cos(dec * np.pi / 180.0) * 60.0)
    dy = np.cos(theta) * length / 60.0
    coords = np.array([[ra_l, ra_l + dx, ra_r + dx,
                        ra_r - dx, ra_l - dx, ra_l],
                      [dec_l, dec_l + dy, dec_r + dy,
                       dec_r - dy, dec_l - dy, dec_l]])
    plot.show_lines([coords], color=color, linewidth=linewidth, alpha=alpha)
    return plot


# draw slits and reference boxes for MOS
def mos_plot(plot, slits, refs, pa):
    # draw the slits
    for slit in slits:
        if 'tilt' in slit.attributes:
            tilt = float(slit.attributes['tilt'].value)
        else:
            tilt = 0.0
        draw_box(plot,
                 pa + tilt,
                 float(slit.attributes['width'].value) / 60.0,
                 float(slit.attributes['length'].value) / 60.0,
                 float(slit.attributes['xce'].value),
                 float(slit.attributes['yce'].value),
                 color='r')
    # make bigger boxes around the reference objects
    for ref in refs:
        draw_box(plot,
                 pa,
                 5.0 / 60.0,
                 5.0 / 60.0,
                 float(ref.attributes['xce'].value),
                 float(ref.attributes['yce'].value),
                 color=(1, 1, 0),
                 linewidth=2)
    return plot


# set up basic plot
def init_plot(hdu, imserver, title, ra, dec, pa):
    servname = {}
    servname['poss2ukstu_red'] = "POSS2/UKSTU Red"
    servname['poss2ukstu_blue'] = "POSS2/UKSTU Blue"
    servname['poss2ukstu_ir'] = "POSS2/UKSTU IR"
    servname['poss1_blue'] = "POSS1 Blue"
    servname['poss1_red'] = "POSS1 Red"

    out = sys.stdout
    sys.stdout = open("/dev/null", 'w')
    plot = aplpy.FITSFigure(hdu)
    plot.show_grayscale()
    plot.set_theme('publication')
    sys.stdout = out

    plot.add_label(0.95, -0.05, "PA = %.1f" % pa,
                   relative=True, style='italic', weight='bold')

    plot.add_label(0.5, 1.03, title,
                   relative=True, style='italic', weight='bold', size='large')
    plot.add_label(-0.05, -0.05, "%s" % servname[imserver],
                   relative=True, style='italic', weight='bold')

    plot.add_grid()
    plot.grid.set_alpha(0.2)
    plot.grid.set_color('b')

    plot.show_circles([ra, ra], [dec, dec], [4.0 / 60.0, 5.0 / 60.0],
                      edgecolor='g')
    draw_box(plot, 0.0, 4.9, 4.9, ra, dec, color='g')
    plot.add_label(0.79,
                   0.79,
                   "RSS",
                   relative=True,
                   style='italic',
                   weight='bold',
                   size='large',
                   horizontalalignment='left',
                   color=(0, 0, 1))
    plot.add_label(0.86,
                   0.86,
                   "SCAM",
                   relative=True,
                   style='italic',
                   weight='bold',
                   size='large',
                   horizontalalignment='left',
                   color=(0, 0, 1))
    plot.add_label(0.75,
                   0.5,
                   "BCAM",
                   relative=True,
                   style='italic',
                   weight='bold',
                   size='large',
                   horizontalalignment='left',
                   color=(0, 0, 1))
    plot.add_label(ra,
                   dec + 4.8 / 60.0,
                   "N",
                   style='italic',
                   weight='bold',
                   size='large',
                   color=(0, 0.5, 1))
    plot.add_label(ra + 4.8 / (np.abs(np.cos(dec * np.pi / 180.0)) * 60),
                   dec,
                   "E",
                   style='italic',
                   weight='bold',
                   size='large',
                   horizontalalignment='right',
                   color=(0, 0.5, 1))
    plot = draw_line(plot, 0, 8, ra, dec, color='g', linewidth=0.5, alpha=1.0)
    plot = draw_line(plot, 90, 8, ra, dec, color='g', linewidth=0.5, alpha=1.0)
    return plot
