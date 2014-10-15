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
if ADDON.getSetting('use_remote_db') == 'false' or ADDON.getSetting('enable_upgrade') == 'true':
    db_connection.init_database()

class Service(xbmc.Player):
    def __init__(self, *args, **kwargs):
        log_utils.log('Service: starting...')
        xbmc.Player.__init__(self, *args, **kwargs)
        self.win = xbmcgui.Window(10000)
        self.reset()

    def reset(self):
        log_utils.log('Service: Resetting...')
        self.win.clearProperty('salts.playing')
        self.win.clearProperty('salts.playing.slug')
        self.win.clearProperty('salts.playing.season')
        self.win.clearProperty('salts.playing.episode')
        self.win.clearProperty('salts.playing.srt')
        self.tracked = False    
        self._totalTime = 999999
        self.slug = None
        self.season = None
        self.episode = None

    def onPlayBackStarted(self):
        log_utils.log('Service: Playback started')
        playing = self.win.getProperty('salts.playing')=='True'
        self.slug = self.win.getProperty('salts.playing.slug')
        self.season = self.win.getProperty('salts.playing.season')
        self.episode = self.win.getProperty('salts.playing.episode')
        srt_path = self.win.getProperty('salts.playing.srt')
        if playing: #Playback is ours
            log_utils.log('Service: tracking progress...')
            self.tracked = True
            if srt_path:
                log_utils.log('Service: Enabling subtitles: %s' % (srt_path))
                self.setSubtitles(srt_path)
            else:
                self.showSubtitles(False)

        self._totalTime=0
        while self._totalTime == 0:
            xbmc.sleep(1000)
            self._totalTime = self.getTotalTime()
            log_utils.log("Total Time: %s" % (self._totalTime), xbmc.LOGDEBUG)

    def onPlayBackStopped(self):
        log_utils.log('Service: Playback Stopped')
        if self.tracked:
            playedTime = float(self._lastPos)
            try: percent_played = int((playedTime / self._totalTime) * 100)
            except: percent_played=0 # guard div by zero
            pTime = utils.format_time(playedTime)
            tTime = utils.format_time(self._totalTime)
            log_utils.log('Service: Played %s of %s total = %s%%' % (pTime, tTime, percent_played), xbmc.LOGDEBUG)
            if playedTime == 0 and self._totalTime == 999999:
                log_utils.log('XBMC silently failed to start playback', xbmc.LOGWARNING)
            elif playedTime>0:
                log_utils.log('Service: Setting bookmark on |%s|%s|%s| to %s seconds' % (self.slug, self.season, self.episode, playedTime), xbmc.LOGDEBUG)
                db_connection.set_bookmark(self.slug, playedTime, self.season, self.episode)
                if percent_played>=75:
                    if xbmc.getCondVisibility('System.HasAddon(script.trakt)'):
                        run = 'RunScript(script.trakt, action=sync, silent=True)'
                        xbmc.executebuiltin(run)
            self.reset()

    def onPlayBackEnded(self):
        log_utils.log('Service: Playback completed')
        self.onPlayBackStopped()
            
monitor = Service()
utils.do_startup_task(MODES.UPDATE_SUBS)

while not xbmc.abortRequested:
    isPlaying = monitor.isPlaying()
    utils.do_scheduled_task(MODES.UPDATE_SUBS, isPlaying)
    if monitor.tracked and monitor.isPlayingVideo():
        monitor._lastPos = monitor.getTime()

    xbmc.sleep(1000)
log_utils.log('Service: shutting down...')
