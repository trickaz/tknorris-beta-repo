"""
    SALTS XBMC Addon
    Copyright (C) 2014 tknorris

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
import xbmc
import xbmcaddon
import xbmcgui
from salts_lib import log_utils
from salts_lib import utils
from salts_lib.constants import MODES
from salts_lib.db_utils import DB_Connection

ADDON = xbmcaddon.Addon(id='plugin.video.salts')
log_utils.log('Service: Installed Version: %s' % (ADDON.getAddonInfo('version')))

db_connection = DB_Connection()
db_connection.init_database()

class Service(xbmc.Player):
    def __init__(self, *args, **kwargs):
        log_utils.log('Service: starting...')
        xbmc.Player.__init__(self, *args, **kwargs)
        self.win = xbmcgui.Window(10000)
        self.reset()

    def reset(self):
        log_utils.log('Service: Resetting...')
        self.win.clearProperty('salts.playing.srt')
        self.tracked = False    

    def onPlayBackStarted(self):
        log_utils.log('Service: Playback started')
        srt_path = self.win.getProperty('salts.playing.srt')
        if srt_path: #Playback is ours
            log_utils.log('Service: tracking progress...')
            self.tracking = True
            if srt_path:
                xbmc.log('1Channel: Service: Enabling subtitles: %s' % (srt_path))
                self.setSubtitles(srt_path)

    def onPlayBackStopped(self):
        log_utils.log('Service: Playback Stopped')
        self.reset()

    def onPlayBackEnded(self):
        log_utils.log('Service: Playback completed')
        self.onPlayBackStopped()
            
monitor = Service()
utils.do_startup_task(MODES.UPDATE_SUBS)

while not xbmc.abortRequested:
    isPlaying = monitor.isPlaying()
    utils.do_scheduled_task(MODES.UPDATE_SUBS, isPlaying)
    xbmc.sleep(1000)
log_utils.log('Service: shutting down...')
