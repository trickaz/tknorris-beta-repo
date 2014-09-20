__all__ = ['scraper', 'dummy_scraper', 'pw_scraper', 'uflix_scraper', 'watchseries_scraper', 'movie25_scraper', 'merdb_scraper', '2movies_scraper', 'icefilms_scraper', 'afdah_scraper', 
           'istreamhd_scraper', 'movieshd_scraper', 'simplymovies_scraper', 'yifytv_scraper', 'viooz_scraper', 'filmstreaming_scraper', 'allucto_scraper', 'onlinemovies_scraper',
           'oneclick_scraper']

import re
import os
import xbmcaddon
import xbmc
from salts_lib import log_utils
from salts_lib.constants import VIDEO_TYPES
from . import scraper # just to avoid editor warning
from . import *

class ScraperVideo:
    def __init__(self, video_type, title, year, season='', episode='', ep_title=''):
        assert(video_type in (VIDEO_TYPES.__dict__[k] for k in VIDEO_TYPES.__dict__ if not k.startswith('__')))
        self.video_type=video_type
        self.title=title
        self.year=year
        self.season=season
        self.episode=episode
        self.ep_title=ep_title
    
    def __str__(self):
        return '|%s|%s|%s|%s|%s|%s|' % (self.video_type, self.title, self.year, self.season, self.episode, self.ep_title)

def update_settings():
    path=xbmcaddon.Addon().getAddonInfo('path')
    full_path = os.path.join(path, 'resources', 'settings.xml')
    try:
        with open(full_path, 'r') as f:
            xml=f.read()
    except:
        raise
    
    match = re.search('(<category label="Scrapers">.*?</category>)', xml, re.DOTALL | re.I)
    if match:
        old_settings=match.group(1)
        
        new_settings = '<category label="Scrapers">\n'
        classes=scraper.Scraper.__class__.__subclasses__(scraper.Scraper)
        for cls in classes:
            for setting in cls.get_settings(): new_settings += setting + '\n'
        new_settings += '    </category>'
            
        if old_settings != new_settings:
            xml=xml.replace(old_settings, new_settings)
            try:
                with open(full_path, 'w') as f:
                    f.write(xml)
            except:
                raise
        else:
            log_utils.log('No Settings Update Needed', xbmc.LOGDEBUG)
    else:
        log_utils.log('Failed to match scraper category in settings.xml', xbmc.LOGWARNING)

update_settings()