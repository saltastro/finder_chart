#!/home/tim/pyTEP/bin/python

import cgi
import cgitb
import sys
import ephem
import json
import MySQLdb as mdb
import numpy as np

def rad2deg(ang):
    return ang*180.0/np.pi

def rad2hrs(time):
    return rad2deg(float(time))/15.0

# set up ephem Observer for the SALT site
def salt_site():
    salt = ephem.Observer()
    salt.lat = "-32:22:32"
    salt.long = "20:48:30"
    salt.elevation = 1800
    salt.temp = 10
    salt.compute_pressure()
    salt.horizon = '0'
    salt.date = ephem.now()
    return salt

def visibility_times(row):
    estart = row['EstripS']
    estop = row['EstripE']
    wstart = row['WstripS']
    wstop = row['WstripE']

def sast(time):
    return ephem.localtime(time).strftime("%Y-%m-%d %H:%M")

def lst2sast(sunset, sunset_lst, lst):
    diff = lst - sunset_lst
    if diff < 0:
        diff = diff + 24
    return sast(ephem.date(sunset + diff*ephem.hour))

def mkquery(sunset, e_twilight, m_twilight, e_twilight_st, m_twilight_st):
    qry = """
                        <= '{sunset}' OR
  			(LastObserved IS NULL OR WaitDays <= 1)) and
  			MaxSeeing <= 7.750000 and MaxSeeing >= 0.000
			AND 
			(
                        (EstripS < {m_twilight_st} AND EstripE > {e_twilight_st})
  			OR 
			(EstripS < {m_twilight_st}+24 AND EstripE > {e_twilight_st}+24) 
			OR 
			(WstripS < {m_twilight_st} AND WstripE > {e_twilight_st}) 
			OR 
			(WstripS < {m_twilight_st}+24 AND WstripE > {e_twilight_st}+24)
			OR 
			(EstripS < {m_twilight_st}+24 AND WstripE > {e_twilight_st} AND WstripS IS NULL ) 
			OR
  			(EstripS < {m_twilight_st}+24 AND WstripE > {e_twilight_st}+24 AND WstripS IS NULL)
                        )
			AND
  			(
                        (TimeRestricted.ObsWindowStart <= '{sunset}'
			AND 
			TimeRestricted.ObsWindowEnd >= '{sunset}') 
			OR
  			(TimeRestricted.ObsWindowStart >= '{sunset}' 
			AND 
			TimeRestricted.ObsWindowEnd <= '{m_twilight}') 
			OR
  			(TimeRestricted.ObsWindowStart <= '{m_twilight}'
			AND 
			TimeRestricted.ObsWindowEnd >= '{m_twilight}')
                        """
    return qry.format(**locals())

##############################

form = cgi.FieldStorage()

salt = salt_site()
sun = ephem.Sun()

fp = open("query_header.txt", 'r')
header = fp.read()
fp.close()
fp = open("query_footer.txt", 'r')
footer = fp.read()
fp.close()

salt = salt_site()
salt.date = ephem.date(form.getvalue("from")) + 0.5

sun = ephem.Sun()
sun.compute(salt)

sunset = salt.next_setting(sun)
salt.date = sunset
sunset_st = rad2hrs(salt.sidereal_time())

salt.horizon = '-18'
e_twilight = salt.next_setting(sun)
salt.date = e_twilight
e_twilight_st = rad2hrs(salt.sidereal_time())

m_twilight = salt.next_rising(sun)
salt.date = m_twilight
m_twilight_st = rad2hrs(salt.sidereal_time())

#print "Sunset: %s" % sast(sunset)
#print "E Twilight: %s" % sast(e_twilight)
#print "M Twilight: %s" % sast(m_twilight)

#print "Sunset ST: %f" % sunset_st
#print "E Twilight ST: %f" % e_twilight_st
#print "M Twilight ST: %f" % m_twilight_st

query = mkquery(sast(sunset), e_twilight, m_twilight, e_twilight_st, m_twilight_st)

str = header + query + footer

con = mdb.connect("sdb.salt", 'salt', 'salt', 'sdb')

with con:
    cur = con.cursor(mdb.cursors.DictCursor)
    cur.execute(str)
    rows = cur.fetchall()

blocks = {}
for row in rows:
    if row['Proposal_Code'][0:6] == "2012-1":
        blocks[row['Block_Id']] = row

sched = []

for block in blocks.keys():
    row = blocks[block]
    s = {}
    if row['Mode'] == None:
        row['Mode'] = 'Salticam'
    desc = """<b><a href="http://wm.salt.saao.ac.za/proposal/%s/" target="_blank">%s</a></b> <br />
    <b>Block:</b> <a href="http://wm.salt.saao.ac.za/block/%s/" target="_blank">%s</a><br />
    <b>Mode:</b> %s <br />
    <b>Target:</b> %s <br />
    <b>Transparency:</b> %s <br />
    <b>Seeing:</b> %s <br />
    <b>Mag:</b> %s <br />
    <b>RA</b> = %s:%s:%s <br />
    <b>DEC</b> = %s%s:%s:%s <br />""" % (row['Proposal_Code'], row['Proposal_Code'],
    row['Block_Id'], row['Block_Id'],
    row['Mode'],
    row['Target_Name'],
    row['Transparency'],
    row['MaxSeeing'],
    row['MaxMag'],
    row['RaH'],
    row['RaM'],
    row['RaS'],
    row['DecSign'],
    row['DecD'],
    row['DecM'],
    row['DecS'])
    s["details"] = desc
    s["section_id"] = row['Priority']
    moon = row['Moon']
    if moon == 'Bright':
        s["color"] = "white"
        s['textColor'] = "black"
    elif moon == 'Gray':
        s["color"] = "Grey"
        s['textColor'] = "white"
    elif moon == 'Dark':
        s['color'] = "Black"
        s['textColor'] = "White"
    else:
        s['color'] = "pink"
        s['textColor'] = "purple"
            
    
    if not row['EstripE'] and not row['WstripS']:
#        print "\t Visibility: %s -- %s" % (lst2sast(sunset, sunset_st, row['EstripS']),
#                                           lst2sast(sunset, sunset_st, row['WstripE']))
        s["start_date"] = "%s" % lst2sast(sunset, sunset_st, row['EstripS'])
        s["end_date"] = "%s" % lst2sast(sunset, sunset_st, row['WstripE'])
        if row['DecD'] > 32:
            s["text"] = "%s South" % row['Block_Id']
        else:
            s["text"] = "%s North" % row['Block_Id']
        sched.append(s)
    else:
#        print "\t East Track: %s -- %s" % (lst2sast(sunset, sunset_st, row['EstripS']),
#                                           lst2sast(sunset, sunset_st, row['EstripE']))
        s["start_date"] = "%s" % lst2sast(sunset, sunset_st, row['EstripS'])
        s["end_date"] = "%s" % lst2sast(sunset, sunset_st, row['EstripE'])
        s["text"] = "%s East" % row['Block_Id']
        sched.append(s)
        #        print "\t West Track: %s -- %s" % (lst2sast(sunset, sunset_st, row['WstripS']),
        #                                           lst2sast(sunset, sunset_st, row['WstripE']))
        s2 = s.copy()
        s2["start_date"] = "%s" % lst2sast(sunset, sunset_st, row['WstripS'])
        s2["end_date"] = "%s" % lst2sast(sunset, sunset_st, row['WstripE'])
        s2["text"] = "%s West" % row['Block_Id']
        sched.append(s2)

print "Content-Type: application/json"
print ""
#json.dump(sched, js, sort_keys=True, indent=4)
json.dump(sched, sys.stdout)
