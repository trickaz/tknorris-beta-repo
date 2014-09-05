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
from salts_lib import log_utils
from salts_lib import utils
from salts_lib.constants import MODES
from salts_lib.db_utils import DB_Connection

ADDON = xbmcaddon.Addon(id='plugin.video.salts')
log_utils.log('Service: Installed Version: %s' % (ADDON.getAddonInfo('version')))

db_connection = DB_Connection()
db_connection.init_database()
player=xbmc.Player()

utils.do_startup_task(MODES.UPDATE_SUBS)
while not xbmc.abortRequested:
    isPlaying = player.isPlaying()
    utils.do_scheduled_task(MODES.UPDATE_SUBS, isPlaying)
    xbmc.sleep(1000)
log_utils.log('Service: shutting down...')
