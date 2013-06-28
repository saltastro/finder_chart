#!/usr/bin/env python
# -*- coding: utf-8 -*-

import cStringIO
import sys
import xml
import base64
import urllib2
import xml.dom.minidom
import pyfits
import numpy as np
import aplpy
import time


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
        tilt = 0.0
        if 'tilt' in slit.attributes:
            tilt = float(slit.attributes['tilt'].value)
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


# read in an ephem file for non-siderial targets
# the start and end times to be plotted are required
def read_ephem(ephemfilename, startTime, endTime):
    ephData = np.loadtxt(ephemfilename,
                         dtype=({'names': ('times',
                                           'RAhr',
                                           'RAmin',
                                           'RAsec',
                                           'Decdeg',
                                           'Decmin',
                                           'Decsec',
                                           'RaRate',
                                           'DecRate'),
                                 'formats': ('S100',
                                             np.float,
                                             np.float,
                                             np.float,
                                             np.float,
                                             np.float,
                                             np.float,
                                             np.float,
                                             np.float)}),
                         delimiter=' ',
                         skiprows=2)

    times = []
    for i in ephData:
        times.append(time.mktime(time.strptime(i['times'],
                                               '%Y-%m-%dT%H:%M:%S')))

    times = np.array(times)

    req_startTime = time.mktime(time.strptime(startTime,
                                              '%Y-%m-%dT%H:%M:%S'))
    req_endTime = time.mktime(time.strptime(endTime,
                                            '%Y-%m-%dT%H:%M:%S'))
    # get back the indeces where the time conditions are met
    req_i = np.where((times >= req_startTime) & (times <= req_endTime))

    # create array with the RA and DEC in degrees from the time restriction
    RA =  ephData[req_i]['RAhr'] * 15.0 +\
          ephData[req_i]['RAmin'] / 60.0 +\
          ephData[req_i]['RAsec'] / 3600.0
    DEC = ephData[req_i]['Decdeg'] +\
          ephData[req_i]['Decmin'] / 60.0 +\
          ephData[req_i]['Decsec'] / 3600.0

    # calculate the mean RA/DEC, this will be the centre of the finder chart
    mean_RA = np.mean(RA)
    mean_DEC = np.mean(DEC)

    return mean_RA, mean_DEC, RA, DEC


# plot the object positions as a function of time from the ephem file
def plot_ephem(plot, RA_pos, DEC_pos, startTime, endTime):
    # plot the object positions
    plot.show_markers(RA_pos,
                      DEC_pos,
                      layer='object_path_markers',
                      edgecolor='red',
                      facecolor='none',
                      marker='o',
                      s=12,
                      linestyle='solid')

    # plot the lines that connect the markers
    lv = np.vstack([RA_pos, DEC_pos])
    plot.show_lines([lv],
                    layer='object_path_lines',
                    edgecolor='red',
                    linestyle='solid')

    dra = RA_pos[-1] - RA_pos[-2]
    ddec = DEC_pos[-1] - DEC_pos[-2]

    # plot the arrow at the start time to show direction
    plot.show_arrows(RA_pos[0] - 1.5 * dra,
                     DEC_pos[0] - 1.5 * ddec,
                     dra,
                     ddec,
                     layer='direction_begin',
                     edgecolor='r',
                     facecolor='None',
                     width=3,
                     head_width=8,
                     head_length=6)

    # plot the arrow at the end time to show the direction
    plot.show_arrows(RA_pos[-1] + dra / 2.0,
                     DEC_pos[-1] + ddec / 2.0,
                     dra,
                     ddec,
                     layer='direction_end',
                     edgecolor='r',
                     facecolor='None',
                     width=3,
                     head_width=8,
                     head_length=6)

    # add the start time label
    plot.add_label(RA_pos[0] - 0.002,
                   DEC_pos[0],
                   startTime.replace('T', ' '),
                   relative=False,
                   size='8',
                   horizontalalignment='left',
                   color=(0, 0, 1))

    # add the end time label
    plot.add_label(RA_pos[-1] - 0.002,
                   DEC_pos[-1],
                   endTime.replace('T', ' '),
                   relative=False,
                   size='8',
                   horizontalalignment='left',
                   color=(0, 0, 1))

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

    plot.add_label(0.95,
                   -0.05,
                   "PA = %.1f" % pa,
                   relative=True,
                   style='italic',
                   weight='bold')

    plot.add_label(0.5,
                   1.03,
                   title,
                   relative=True,
                   style='italic',
                   weight='bold',
                   size='large')
    plot.add_label(-0.05,
                   -0.05,
                   "%s" % servname[imserver],
                   relative=True,
                   style='italic',
                   weight='bold')

    plot.add_grid()
    plot.grid.set_alpha(0.2)
    plot.grid.set_color('b')

    plot.show_circles([ra, ra],
                      [dec, dec],
                      [4.0 / 60.0, 5.0 / 60.0],
                      edgecolor='g')
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
