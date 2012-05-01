#!/home/tim/pyTEP/bin/python

import cgi
import cgitb
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

cgitb.enable()
os.environ['HOME'] = '/tmp/pysalt/matplotlib/'

import matplotlib
matplotlib.use('Agg')

import aplpy
import finder_chart as finder

form = cgi.FieldStorage()

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
      print "Content-Type: text/html"
      print ""
      print "Please specify MOS XML file."
      exit()

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
   try:
      propid = form.getvalue("prop")
      pi_name = form.getvalue("pi")
      obj = form.getvalue("objname")
      ra = 180.0*ephem.hours(form.getvalue("ra"))/np.pi
      dec = ephem.degrees(form.getvalue("dec"))*180.0/np.pi
      pa = float(form.getvalue("pa"))
      title = "%s (%s; %s)" % (obj, propid, pi_name)
   except:
      print "Content-Type: text/html"
      print ""
      print "<PRE>"
      print "Prop ID: %s" % propid
      print "PI: %s" % pi_name
      print "Object: %s" % object
      print "RA: %f" % ra
      print "Dec: %f" % dec
      print "PA: %f" % pa
      print "Please specify all fields."
      print "</PRE>"
      exit() 

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

print "Content-Type: image/%s" % output
#if output != 'png':
if mode == "mos":
   print "Content-Disposition: attachment; filename=%s.%s" % (barcode, output)
else:
   print "Content-Disposition: attachment; filename=%s.%s" % (obj, output)
print ""

# Send the actual image data
sys.stdout.write(plotData.read())
