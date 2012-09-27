#!/home/tim/pyTEP/bin/python

import cgi
import cgitb
import cStringIO
import os
import sys
import traceback
import xml
import base64
import urllib2
import xml.dom.minidom
import pyfits
import ephem
import numpy as np

cgitb.enable()

# stupid matplotlib requires a home dir somewhere.....
mpl_homedir = '/tmp/pysalt_matplotlib/'
if not os.path.exists(mpl_homedir):
    os.mkdir(mpl_homedir)
os.environ['HOME'] = mpl_homedir

import matplotlib
matplotlib.use('Agg')

import aplpy
import finder_chart as finder

form = cgi.FieldStorage()

def generate_finder_chart():

    # get parameters from web form
    mode = form.getvalue("mode")
    imserver = form.getvalue("image")
    output = form.getvalue("output")

    if mode == "mos":
        if form.has_key("xml"):
            fileitem = form["xml"]
            mask_xml = fileitem.file.read()
            doc = xml.dom.minidom.parseString(mask_xml)
            barcode = ''
        else:
            raise Exception("Please specify MOS XML file.")

        pars = doc.getElementsByTagName("parameter")
        slits = doc.getElementsByTagName("slit")
        refs = doc.getElementsByTagName("refstar")

        parameters = {}

        for par in pars:
            name = par.getAttribute("name")
            val = par.getAttribute("value")
            parameters[name] = val

        ra = float(parameters["CENTERRA"])
        dec = float(parameters["CENTERDEC"])
        pa = float(parameters["ROTANGLE"])
        propcode = parameters["PROPOSALCODE"]
        pi_email = parameters["PI"]
        barcode = "Mask #%s" % parameters["MASKNUM"]
        title = "%s (%s; %s)" % (barcode, propcode, pi_email)
    else:
        propid = form.getvalue("prop")
        pi_name = form.getvalue("pi")
        obj = form.getvalue("objname")
        ra = 180.0*ephem.hours(form.getvalue("ra"))/np.pi
        dec = ephem.degrees(form.getvalue("dec"))*180.0/np.pi
        pa = float(form.getvalue("pa"))
        title = "%s (%s; %s)" % (obj, propid, pi_name)

    if form.has_key("fits"):
        hdu = finder.get_fits(form["fits"].value)
    else:
        hdu = finder.get_dss(imserver, ra, dec)

    plot = finder.init_plot(hdu, imserver, title, ra, dec, pa)

    if mode == "mos":
        plot = finder.mos_plot(plot, slits, refs, pa)

    if mode == "ls":
        plot = finder.draw_line(plot, pa, 8.0, ra, dec, color='r', linewidth=3, alpha=0.5)

    if mode == "slot":
        plot = finder.draw_box(plot, pa+90, 2.0/6.0, 10.0, ra, dec, color='r', linewidth=2, alpha=0.5)

    plotData = cStringIO.StringIO()
    plot.save(plotData, format=output)
    plotData.seek(0)

    if output == 'pdf':
        mime = 'application/pdf'
    else:
        mime = 'image/%s' % output
    print "Content-Type: %s" % mime
    #if output != 'png':
    if mode == "mos":
        print "Content-Disposition: attachment; filename=%s.%s" % (barcode, output)
    else:
        print "Content-Disposition: attachment; filename=%s.%s" % (obj, output)
    print ""

    # Send the actual image data
    sys.stdout.write(plotData.read())

try:
    generate_finder_chart()
except Exception, e:
    print "Status: 406 Insufficient or wrong parameters"
    print "Content-Type: text/plain"
    print ""
    print "<PRE>"
    print "Prop ID: %s" % form["prop"]
    print "PI: %s" % form["pi"]
    print "Object: %s" % form["objname"]
    print "RA: %s" % form["ra"]
    print "Dec: %s" % form["dec"]
    print "PA: %s" % form["pa"]
    print "Please specify all fields."
    print "</PRE>"
