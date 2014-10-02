import os
import time
import _strptime
import re
import datetime
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import log_utils
import sys
import hashlib
from constants import *
from scrapers import * # import all scrapers into this namespace
from addon.common.addon import Addon
from trakt_api import Trakt_API
from db_utils import DB_Connection

ADDON = Addon('plugin.video.salts')
ICON_PATH = os.path.join(ADDON.get_path(), 'icon.png')
SORT_FIELDS =  [(SORT_LIST[int(ADDON.get_setting('sort1_field'))], SORT_SIGNS[ADDON.get_setting('sort1_order')]),
                (SORT_LIST[int(ADDON.get_setting('sort2_field'))], SORT_SIGNS[ADDON.get_setting('sort2_order')]),
                (SORT_LIST[int(ADDON.get_setting('sort3_field'))], SORT_SIGNS[ADDON.get_setting('sort3_order')]),
                (SORT_LIST[int(ADDON.get_setting('sort4_field'))], SORT_SIGNS[ADDON.get_setting('sort4_order')])]

username=ADDON.get_setting('username')
password=ADDON.get_setting('password')
use_https=ADDON.get_setting('use_https')=='true'
trakt_timeout=int(ADDON.get_setting('trakt_timeout'))

P_MODE = int(ADDON.get_setting('parallel_mode'))
if P_MODE == P_MODES.THREADS:
    import threading
    from Queue import Queue, Empty
elif P_MODE == P_MODES.PROCESSES:
    try:
        import multiprocessing
        from multiprocessing import Queue
        from Queue import Empty
    except ImportError:
        import threading
        from Queue import Queue, Empty
        P_MODE = P_MODES.THREADS
        builtin = 'XBMC.Notification(%s,Process Mode not supported on this platform falling back to Thread Mode, 7500, %s)'
        xbmc.executebuiltin(builtin % (ADDON.get_name(), ICON_PATH))

trakt_api=Trakt_API(username,password, use_https, trakt_timeout)
db_connection=DB_Connection()

THEME_LIST = ['Shine', 'Luna_Blue', 'Iconic']
THEME = THEME_LIST[int(ADDON.get_setting('theme'))]
if xbmc.getCondVisibility('System.HasAddon(script.salts.themepak)'):
    themepak_path = xbmcaddon.Addon('script.salts.themepak').getAddonInfo('path')
else:
    themepak_path=ADDON.get_path()
THEME_PATH = os.path.join(themepak_path, 'art', 'themes', THEME)

def art(name): 
    return os.path.join(THEME_PATH, name)

def choose_list(username=None):
    lists = trakt_api.get_lists(username)
    if username is None: lists.insert(0, {'name': 'watchlist', 'slug': WATCHLIST_SLUG})
    if lists:
        dialog=xbmcgui.Dialog()
        index = dialog.select('Pick a list', [list_data['name'] for list_data in lists])
        if index>-1:
            return lists[index]['slug']
    else:
        builtin = 'XBMC.Notification(%s,No Lists exist for user: %s, 5000, %s)'
        xbmc.executebuiltin(builtin % (ADDON.get_name(), username, ICON_PATH))

def show_id(show):
    queries={}
    if 'imdb_id' in show and show['imdb_id']:
        queries['id_type']='imdb_id'
        queries['show_id']=show['imdb_id']
    elif 'tvdb_id' in show and show['tvdb_id']:
        queries['id_type']='tvdb_id'
        queries['show_id']=show['tvdb_id']
    elif 'tmdb_id' in show and show['tmdb_id']:
        queries['id_type']='tmdb_id'
        queries['show_id']=show['tmdb_id']
    return queries
    
def update_url(video_type, title, year, source, old_url, new_url, season, episode):
    log_utils.log('Setting Url: |%s|%s|%s|%s|%s|%s|%s|%s|' % (video_type, title, year, source, old_url, new_url, season, episode), xbmc.LOGDEBUG)
    if new_url:
        db_connection.set_related_url(video_type, title, year, source, new_url, season, episode)
    else:
        db_connection.clear_related_url(video_type, title, year, source, season, episode)

    # clear all episode local urls if tvshow url changes
    if video_type == VIDEO_TYPES.TVSHOW and new_url != old_url:
        db_connection.clear_related_url(VIDEO_TYPES.EPISODE, title, year, source)
    
def make_season_item(season, fanart):
    label = 'Season %s' % (season['season'])
    season['images']['fanart']=fanart
    liz=make_list_item(label, season)
    liz.setInfo('video', {'season': season['season']})

    menu_items=[]
    liz.addContextMenuItems(menu_items, replaceItems=True)
    return liz

def make_list_item(label, meta):
    art=make_art(meta)
    listitem = xbmcgui.ListItem(label, iconImage=art['thumb'], thumbnailImage=art['thumb'])
    listitem.setProperty('fanart_image', art['fanart'])
    try: listitem.setArt(art)
    except: pass
    if 'imdb_id' in meta: listitem.setProperty('imdb_id', meta['imdb_id'])
    if 'tvdb_id' in meta: listitem.setProperty('tvdb_id', str(meta['tvdb_id']))
    return listitem

def make_art(show, fanart=''):
    if not fanart: fanart = art('fanart.jpg')
    art_dict={'banner': '', 'fanart': fanart, 'thumb': '', 'poster': ''}
    if 'images' in show:
        if 'banner' in show['images']: art_dict['banner']=show['images']['banner']
        if 'fanart' in show['images']: art_dict['fanart']=show['images']['fanart']
        if 'poster' in show['images']: art_dict['thumb']=art_dict['poster']=show['images']['poster']
        if 'screen' in show['images']: art_dict['thumb']=art_dict['poster']=show['images']['screen']
    return art_dict

def make_info(item, show=''):
    #log_utils.log('Making Info: Show: %s' % (show), xbmc.LOGDEBUG)
    #log_utils.log('Making Info: Item: %s' % (item), xbmc.LOGDEBUG)
    info={}
    info['title']=item['title']
    if 'overview' in item: info['plot']=info['plotoutline']=item['overview']
    if 'runtime' in item: info['duration']=item['runtime']
    if 'imdb_id' in item: info['code']=info['imdbnumber']=info['imdb_id']=item['imdb_id']
    if 'tmdb_id' in item: info['tmdb_id']=item['tmdb_id']
    if 'tvdb_id' in item: info['tvdb_id']=item['tvdb_id']
    if 'certification' in item: info['mpaa']=item['certification']
    if 'year' in item: info['year']=item['year']
    if 'season' in item: info['season']=item['season']
    if 'episode' in item: info['episode']=item['episode']
    if 'number' in item: info['episode']=item['number']
    if 'genres' in item: info['genre']=', '.join(item['genres'])
    if 'network' in item: info['studio']=item['network']
    if 'status' in item: info['status']=item['status']
    if 'tagline' in item: info['tagline']=item['tagline']
    if 'watched' in item and item['watched']: info['playcount']=1
    if 'plays' in item and item['plays']: info['playcount']=item['plays']
    
    if 'ratings' in item: 
        info['rating']=int(item['ratings']['percentage'])/10.0
        info['votes']=item['ratings']['votes']

    if 'first_aired_iso' in item or 'first_aired' in item:
        utc_air_time = iso_2_utc(item['first_aired_iso']) if 'first_aired_iso' in item else fa_2_utc(item['first_aired'])
        try: info['aired']=info['premiered']=time.strftime('%Y-%m-%d', time.localtime(utc_air_time))
        except ValueError: # windows throws a ValueError on negative values to localtime  
            d=datetime.datetime.fromtimestamp(0) + datetime.timedelta(seconds=utc_air_time)
            info['aired']=info['premiered']=d.strftime('%Y-%m-%d')
     
    if 'released' in item:
        try: info['premiered']=time.strftime('%Y-%m-%d', time.localtime(item['released']))
        except ValueError: # windows throws a ValueError on negative values to localtime
            d=datetime.datetime.fromtimestamp(0) + datetime.timedelta(seconds=item['released'])
            info['premiered']=d.strftime('%Y-%m-%d')
         

    if 'seasons' in item:
        total_episodes=0
        watched_episodes=0
        for season in item['seasons']:
            if 'aired' in season and 'completed' in season:
                total_episodes += season['aired']
                watched_episodes += season['completed']
            else:
                total_episodes += len(season['episodes'])
                watched_episodes += len(season['episodes'])
        info['episode']=info['TotalEpisodes']=total_episodes
        info['WatchedEpisodes']=watched_episodes
        info['UnWatchedEpisodes']=total_episodes - watched_episodes

    if 'trailer' in item:
        match=re.search('\?v=(.*)', item['trailer'])
        if match:
            info['trailer']='plugin://plugin.video.youtube/?action=play_video&videoid=%s' % (match.group(1)) 

    # override item params with show info if it exists
    if 'certification' in show: info['mpaa']=show['certification']
    if 'year' in show: info['year']=show['year']
    if 'imdb_id' in show: info['code']=info['imdbnumber']=info['imdb_id']=show['imdb_id']
    if 'tmdb_id' in show: info['tmdb_id']=show['tmdb_id']
    if 'tvdb_id' in show: info['tvdb_id']=show['tvdb_id']
    if 'runtime' in show: info['duration']=show['runtime']
    if 'title' in show: info['tvshowtitle']=show['title']
    if 'people' in show: info['cast']=[actor['name'] for actor in show['people']['actors'] if actor['name']]
    if 'people' in show: info['castandrole']=['%s as %s' % (actor['name'],actor['character']) for actor in show['people']['actors'] if actor['name'] and actor['character']]
    return info
    
def get_section_params(section, set_sort=True):
    section_params={}
    section_params['section']=section
    if section==SECTIONS.TV:
        set_view('tvshows', set_sort)
        section_params['next_mode']=MODES.SEASONS
        section_params['folder']=True
        section_params['video_type']=VIDEO_TYPES.TVSHOW
    else:
        set_view('movies', set_sort)
        section_params['next_mode']=MODES.GET_SOURCES
        section_params['folder']=ADDON.get_setting('source-win')=='Directory' and ADDON.get_setting('auto-play')=='false'
        section_params['video_type']=VIDEO_TYPES.MOVIE
    return section_params

def filename_from_title(title, video_type, year=None):
    if video_type == VIDEO_TYPES.TVSHOW:
        filename = '%s S%sE%s.strm'
        filename = filename % (title, '%s', '%s')
    else:
        if year: title = '%s (%s)' % (title, year)
        filename = '%s.strm' % title

    filename = re.sub(r'(?!%s)[^\w\-_\.]', '.', filename)
    filename = re.sub('\.+', '.', filename)
    xbmc.makeLegalFilename(filename)
    return filename

def filter_unknown_hosters(hosters):
    filtered_hosters=[]
    for host in hosters:
        for key, _ in SORT_FIELDS:
            if key in host and host[key] is None:
                break
        else:
            filtered_hosters.append(host)
    return filtered_hosters

def filter_exclusions(hosters):
    exclusions = ADDON.get_setting('excl_list')
    exclusions = exclusions.replace(' ', '')
    exclusions = exclusions.lower()
    if not exclusions: return hosters
    filtered_hosters=[]
    for hoster in hosters:
        if hoster['host'].lower() in exclusions:
            log_utils.log('Excluding %s (%s) from %s' % (hoster['url'], hoster['host'], hoster['class'].get_name()), xbmc.LOGDEBUG)
            continue
        filtered_hosters.append(hoster)
    return filtered_hosters

def get_sort_key(item):
    item_sort_key = []
    for field, sign in SORT_FIELDS:
        if field=='none':
            break
        elif field in SORT_KEYS:
            if field == 'source':
                value=item['class'].get_name()
            else:
                value=item[field]
            
            if value in SORT_KEYS[field]:
                item_sort_key.append(sign*int(SORT_KEYS[field][value]))
            else: # assume all unlisted values sort as worst
                item_sort_key.append(sign*-1)
        else:
            if item[field] is None:
                item_sort_key.append(sign*-1)
            else:
                item_sort_key.append(sign*int(item[field]))
    #print 'item: %s sort_key: %s' % (item, item_sort_key)
    return tuple(item_sort_key)

def make_source_sort_key():
    sso=ADDON.get_setting('source_sort_order')
    sort_key={}
    i=0
    scrapers = relevant_scrapers(include_disabled=True)
    scraper_names = [scraper.get_name() for scraper in scrapers]
    if sso:
        sources = sso.split('|')
        sort_key={}
        for i,source in enumerate(sources):
            if source in scraper_names:
                sort_key[source]=-i
        
    for j, scraper in enumerate(scrapers):
        if scraper.get_name() not in sort_key:
            sort_key[scraper.get_name()]=-(i+j)
    
    return sort_key

def get_source_sort_key(item):
    sort_key=make_source_sort_key()
    return -sort_key[item.get_name()]
        
def make_source_sort_string(sort_key):
    sorted_key = sorted(sort_key.items(), key=lambda x: -x[1])
    sort_string = '|'.join([element[0] for element in sorted_key])
    return sort_string

def start_worker(q, func, args):
    if P_MODE == P_MODES.THREADS:
        worker=threading.Thread(target=func, args=([q] + args))
    elif P_MODE == P_MODES.PROCESSES:
        worker=multiprocessing.Process(target=func, args=([q] + args))
    worker.daemon=True
    worker.start()
    return worker

def reap_workers(workers, timeout=0):
    """
    Reap thread/process workers; don't block by default; return un-reaped workers
    """
    log_utils.log('In Reap: %s' % (workers), xbmc.LOGDEBUG)
    living_workers=[]
    for worker in workers:
        log_utils.log('Reaping: %s' % (worker.name), xbmc.LOGDEBUG)
        worker.join(timeout)
        if worker.is_alive():
            log_utils.log('Worker %s still running' % (worker.name), xbmc.LOGDEBUG)
            living_workers.append(worker)
    return living_workers

def parallel_get_sources(q, cls, video):
    scraper_instance=cls(int(ADDON.get_setting('source_timeout')))
    if P_MODE == P_MODES.THREADS:
        worker=threading.current_thread()
    elif P_MODE == P_MODES.PROCESSES:
        worker=multiprocessing.current_process()
        
    log_utils.log('Starting %s (%s) for %s sources' % (worker.name, worker, cls.get_name()), xbmc.LOGDEBUG)
    hosters=scraper_instance.get_sources(video)
    log_utils.log('%s returned %s sources from %s' % (cls.get_name(), len(hosters), worker), xbmc.LOGDEBUG)
    result = {'name': cls.get_name(), 'hosters': hosters}
    q.put(result)

def parallel_get_url(q, cls, video):
    scraper_instance=cls(int(ADDON.get_setting('source_timeout')))
    if P_MODE == P_MODES.THREADS:
        worker=threading.current_thread()
    elif P_MODE == P_MODES.PROCESSES:
        worker=multiprocessing.current_process()
        
    log_utils.log('Starting %s (%s) for %s url' % (worker.name, worker, cls.get_name()), xbmc.LOGDEBUG)
    url=scraper_instance.get_url(video)
    log_utils.log('%s returned url %s from %s' % (cls.get_name(), url, worker), xbmc.LOGDEBUG)
    related={}
    related['class']=scraper_instance
    if not url: url=''
    related['url']=url
    related['name']=related['class'].get_name()
    related['label'] = '[%s] %s' % (related['name'], related['url'])
    q.put(related)

# Run a task on startup. Settings and mode values must match task name
def do_startup_task(task):
    run_on_startup=ADDON.get_setting('auto-%s' % task)=='true' and ADDON.get_setting('%s-during-startup' % task) == 'true' 
    if run_on_startup and not xbmc.abortRequested:
        log_utils.log('Service: Running startup task [%s]' % (task))
        now = datetime.datetime.now()
        xbmc.executebuiltin('RunPlugin(plugin://%s/?mode=%s)' % (ADDON.get_id(), task))
        db_connection.set_setting('%s-last_run' % (task), now.strftime("%Y-%m-%d %H:%M:%S.%f"))
    
# Run a recurring scheduled task. Settings and mode values must match task name
def do_scheduled_task(task, isPlaying):
    now = datetime.datetime.now()
    if ADDON.get_setting('auto-%s' % task) == 'true':
        next_run=get_next_run(task)
        #log_utils.log("Update Status on [%s]: Currently: %s Will Run: %s" % (task, now, next_run), xbmc.LOGDEBUG)
        if now >= next_run:
            is_scanning = xbmc.getCondVisibility('Library.IsScanningVideo')
            if not is_scanning:
                during_playback = ADDON.get_setting('%s-during-playback' % (task))=='true'
                if during_playback or not isPlaying:
                    log_utils.log('Service: Running Scheduled Task: [%s]' % (task))
                    builtin = 'RunPlugin(plugin://%s/?mode=%s)' % (ADDON.get_id(), task)
                    xbmc.executebuiltin(builtin)
                    db_connection.set_setting('%s-last_run' % task, now.strftime("%Y-%m-%d %H:%M:%S.%f"))
                else:
                    log_utils.log('Service: Playing... Busy... Postponing [%s]' % (task), xbmc.LOGDEBUG)
            else:
                log_utils.log('Service: Scanning... Busy... Postponing [%s]' % (task), xbmc.LOGDEBUG)

def get_next_run(task):
    # strptime mysteriously fails sometimes with TypeError; this is a hacky workaround
    # note, they aren't 100% equal as time.strptime loses fractional seconds but they are close enough
    try:
        last_run_string = db_connection.get_setting(task+'-last_run')
        if not last_run_string: last_run_string=LONG_AGO
        last_run=datetime.datetime.strptime(last_run_string, "%Y-%m-%d %H:%M:%S.%f")
    except (TypeError, ImportError):
        last_run=datetime.datetime(*(time.strptime(last_run_string, '%Y-%m-%d %H:%M:%S.%f')[0:6]))
    interval=datetime.timedelta(hours=float(ADDON.get_setting(task+'-interval')))
    return (last_run+interval)

def url_exists(video):
    """
    check each source for a url for this video; return True as soon as one is found. If none are found, return False
    """
    max_timeout = int(ADDON.get_setting('source_timeout'))
    log_utils.log('Checking for Url Existence: |%s|' % (video), xbmc.LOGDEBUG)
    for cls in relevant_scrapers(video.video_type):
        if ADDON.get_setting('%s-sub_check' % (cls.get_name()))=='true':
            scraper_instance=cls(max_timeout)
            url = scraper_instance.get_url(video)
            if url:
                log_utils.log('Found url for |%s| @ %s: %s' % (video, cls.get_name(), url), xbmc.LOGDEBUG)
                return True

    log_utils.log('No url found for: |%s|' % (video))
    return False

def relevant_scrapers(video_type=None, include_disabled=False, order_matters=False):
    classes=scraper.Scraper.__class__.__subclasses__(scraper.Scraper)
    relevant=[]
    for cls in classes:
        if video_type is None or video_type in cls.provides():
            if include_disabled or scraper_enabled(cls.get_name()):
                relevant.append(cls)
    
    if order_matters:
        relevant.sort(key=get_source_sort_key)
    return relevant

def scraper_enabled(name):
    # return true if setting exists and set to true, or setting doesn't exist (i.e. '')
    return ADDON.get_setting('%s-enable' % (name)) in ['true', '']

def set_view(content, set_sort):
    # set content type so library shows more views and info
    if content:
        xbmcplugin.setContent(int(sys.argv[1]), content)

    # set sort methods - probably we don't need all of them
    if set_sort:
        xbmcplugin.addSortMethod(handle=int(sys.argv[1]), sortMethod=xbmcplugin.SORT_METHOD_UNSORTED)
        xbmcplugin.addSortMethod(handle=int(sys.argv[1]), sortMethod=xbmcplugin.SORT_METHOD_LABEL)
        xbmcplugin.addSortMethod(handle=int(sys.argv[1]), sortMethod=xbmcplugin.SORT_METHOD_VIDEO_RATING)
        xbmcplugin.addSortMethod(handle=int(sys.argv[1]), sortMethod=xbmcplugin.SORT_METHOD_DATE)
        xbmcplugin.addSortMethod(handle=int(sys.argv[1]), sortMethod=xbmcplugin.SORT_METHOD_PROGRAM_COUNT)
        xbmcplugin.addSortMethod(handle=int(sys.argv[1]), sortMethod=xbmcplugin.SORT_METHOD_VIDEO_RUNTIME)
        xbmcplugin.addSortMethod(handle=int(sys.argv[1]), sortMethod=xbmcplugin.SORT_METHOD_GENRE)

def make_day(date):
    try: date=datetime.datetime.strptime(date,'%Y-%m-%d').date()
    except TypeError: date = datetime.datetime(*(time.strptime(date, '%Y-%m-%d')[0:6])).date()
    today=datetime.date.today()
    day_diff = (date - today).days
    if day_diff == -1:
        date='Yesterday'
    elif day_diff == 0:
        date='Today'
    elif day_diff == 1:
        date='Tomorrow'
    elif day_diff > 1 and day_diff < 7:
        date = date.strftime('%A')

    return date

def iso_2_utc(iso_ts):
    if not iso_ts or iso_ts is None: return 0
    delim = iso_ts.rfind('+')
    if delim == -1:  delim = iso_ts.rfind('-')
    
    if delim>-1:
        ts = iso_ts[:delim]
        sign = iso_ts[delim]
        tz = iso_ts[delim+1:]
    else:
        ts = iso_ts
        tz = None
    
    try: d=datetime.datetime.strptime(ts,'%Y-%m-%dT%H:%M:%S')
    except TypeError: d = datetime.datetime(*(time.strptime(ts, '%Y-%m-%dT%H:%M:%S')[0:6]))
    
    hours, minutes = tz.split(':')
    hours = int(hours)
    minutes= int(minutes)
    if sign == '-':
        hours = -hours
        minutes = -minutes
    dif = datetime.timedelta(minutes=minutes, hours=hours)
    utc_dt = d - dif
    epoch = datetime.datetime.utcfromtimestamp(0)
    delta = utc_dt - epoch
    try: seconds = delta.total_seconds() # works only on 2.7
    except: seconds = delta.seconds + delta.days * 24 * 3600 # close enough
    return seconds

def fa_2_utc(first_aired):
    """
    This should only require subtracting off the difference between PST and UTC, but it doesn't
    and I don't know why. Regardless, this works.
    """
    # dif in seconds between local timezone and gmt timezone
    utc_dif = time.mktime(time.gmtime()) - time.mktime(time.localtime())
    return first_aired - (8*60*60 - utc_dif)

def valid_account():
    username=ADDON.get_setting('username')
    password=ADDON.get_setting('password')
    last_hash=ADDON.get_setting('last_hash')
    cur_hash = hashlib.md5(username+password).hexdigest()
    if cur_hash != last_hash:
        try:
            valid_account=trakt_api.valid_account()
        except:
            valid_account=False
        log_utils.log('Checked valid account (%s): %s != %s' % (valid_account, last_hash, cur_hash), xbmc.LOGDEBUG)

        if valid_account:
            ADDON.set_setting('last_hash', cur_hash)
    else:
        log_utils.log('Assuming valid account: %s == %s' % (last_hash, cur_hash), xbmc.LOGDEBUG)
        valid_account=True
        
    return valid_account

def format_sub_label(sub):
    label = '%s - [%s] - (' % (sub['language'], sub['version'])
    if sub['completed']:
        color='green'
    else:
        label += '%s%% Complete, ' % (sub['percent'])
        color='yellow'
    if sub['hi']: label += 'HI, '
    if sub['corrected']: label += 'Corrected, '
    if sub['hd']: label += 'HD, '
    if not label.endswith('('):
        label = label[:-2] + ')'
    else:
        label = label[:-4]
    label='[COLOR %s]%s[/COLOR]' % (color, label)
    return label

def srt_indicators_enabled():
    return (ADDON.get_setting('enable-subtitles')=='true' and (ADDON.get_setting('subtitle-indicator')=='true'))

def srt_download_enabled():
    return (ADDON.get_setting('enable-subtitles')=='true' and (ADDON.get_setting('subtitle-download')=='true'))

def srt_show_enabled():
    return (ADDON.get_setting('enable-subtitles')=='true' and (ADDON.get_setting('subtitle-show')=='true'))

def format_episode_label(label, season, episode, srts):
    req_hi = ADDON.get_setting('subtitle-hi')=='true'
    req_hd = ADDON.get_setting('subtitle-hd')=='true'
    color='red'
    percent=0
    hi=None
    hd=None
    corrected=None
    
    for srt in srts:
        if str(season)==srt['season'] and str(episode)==srt['episode']:
            if not req_hi or srt['hi']:
                if not req_hd or srt['hd']:
                    if srt['completed']:
                        color='green'
                        if not hi: hi=srt['hi']
                        if not hd: hd=srt['hd']
                        if not corrected: corrected=srt['corrected']
                    elif color!='green':
                        color='yellow'
                        if float(srt['percent'])>percent:
                            if not hi: hi=srt['hi']
                            if not hd: hd=srt['hd']
                            if not corrected: corrected=srt['corrected']
                            percent=srt['percent']
    
    if color!='red':
        label += ' [COLOR %s](SRT: ' % (color)
        if color=='yellow':
            label += ' %s%%, ' % (percent)
        if hi: label += 'HI, '
        if hd: label += 'HD, '
        if corrected: label += 'Corrected, '
        label = label[:-2]
        label+= ')[/COLOR]'
    return label

def get_force_title_list():
    filter_str = ADDON.get_setting('force_title_match')
    filter_list = filter_str.split('|') if filter_str else []
    return filter_list

def calculate_success(name):
    tries=db_connection.get_setting('%s_try' % (name))
    fail = db_connection.get_setting('%s_fail' % (name))
    tries = int(tries) if tries else 0
    fail = int(fail) if fail else 0
    rate = int(round((fail*100.0)/tries)) if tries>0 else 0
    rate = 100 - rate
    return rate

def record_timeouts(fails):
    for key in fails:
        if fails[key]==True:
            log_utils.log('Recording Timeout of %s' % (key), xbmc.LOGWARNING)
            db_connection.increment_db_setting('%s_fail' % key)

def do_disable_check():
    scrapers=relevant_scrapers()
    auto_disable=ADDON.get_setting('auto-disable')
    check_freq=int(ADDON.get_setting('disable-freq'))
    disable_thresh=int(ADDON.get_setting('disable-thresh'))
    for cls in scrapers:
        last_check = db_connection.get_setting('%s_check' % (cls.get_name()))
        last_check = int(last_check) if last_check else 0
        tries=db_connection.get_setting('%s_try' % (cls.get_name()))
        tries = int(tries) if tries else 0
        if tries>0 and tries/check_freq>last_check/check_freq:
            db_connection.set_setting('%s_check' % (cls.get_name()), str(tries))
            success_rate=calculate_success(cls.get_name())
            if success_rate<disable_thresh:
                if auto_disable == DISABLE_SETTINGS.ON:
                    ADDON.set_setting('%s-enable' % (cls.get_name()), 'false')
                    builtin = "XBMC.Notification(%s,[COLOR blue]%s[/COLOR] Scraper Automatically Disabled, 5000, %s)" % (ADDON.get_name(), cls.get_name(), ICON_PATH)
                    xbmc.executebuiltin(builtin)
                elif auto_disable == DISABLE_SETTINGS.PROMPT:
                    dialog=xbmcgui.Dialog()
                    line1='The [COLOR blue]%s[/COLOR] scraper timed out on [COLOR red]%s%%[/COLOR] of %s requests'  % (cls.get_name(), 100-success_rate, tries)
                    line2= 'Each timeout wastes system resources and time.'
                    line3='([I]If you keep it enabled, consider increasing the scraper timeout.[/I])'
                    ret = dialog.yesno('SALTS', line1, line2, line3, 'Keep Enabled', 'Disable It')
                    if ret:
                        ADDON.set_setting('%s-enable' % (cls.get_name()), 'false')

def menu_on(menu):
    return ADDON.get_setting('show_%s' % (menu))=='true'
