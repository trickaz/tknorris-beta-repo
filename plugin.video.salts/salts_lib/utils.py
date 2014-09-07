import time
import re
import datetime
import xbmc
import xbmcgui
import xbmcplugin
import log_utils
import sys
import md5
from constants import *
from scrapers import * # import all scrapers into this namespace
from addon.common.addon import Addon
from trakt_api import Trakt_API
from db_utils import DB_Connection

ADDON = Addon('plugin.video.salts')
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
    import multiprocessing
    from multiprocessing import Queue
    from Queue import Empty

trakt_api=Trakt_API(username,password, use_https, trakt_timeout)
db_connection=DB_Connection()

def choose_list(username=None):
    lists = trakt_api.get_lists(username)
    if username is None: lists.insert(0, {'name': 'watchlist', 'slug': WATCHLIST_SLUG})
    dialog=xbmcgui.Dialog()
    index = dialog.select('Pick a list', [list_data['name'] for list_data in lists])
    if index>-1:
        return lists[index]['slug']

def show_id(show):
    queries={}
    if 'imdb_id' in show:
        queries['id_type']='imdb_id'
        queries['show_id']=show['imdb_id']
    elif 'tvdb_id' in show:
        queries['id_type']='tvdb_id'
        queries['show_id']=show['tvdb_id']
    elif 'tmdb_id' in show:
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
    art={'banner': '', 'fanart': fanart, 'thumb': '', 'poster': ''}
    if 'images' in show:
        if 'banner' in show['images']: art['banner']=show['images']['banner']
        if 'fanart' in show['images']: art['fanart']=show['images']['fanart']
        if 'poster' in show['images']: art['thumb']=art['poster']=show['images']['poster']
        if 'screen' in show['images']: art['thumb']=art['poster']=show['images']['screen']
    return art

def make_info(item, show=''):
    #log_utils.log('Making Info: Show: %s' % (show), xbmc.LOGDEBUG)
    #log_utils.log('Making Info: Item: %s' % (item), xbmc.LOGDEBUG)
    info={}
    info['title']=item['title']
    info['rating']=int(item['ratings']['percentage'])/10.0
    info['votes']=item['ratings']['votes']
    info['plot']=info['plotoutline']=item['overview']
    
    if 'runtime' in item: info['duration']=item['runtime']
    if 'imdb_id' in item: info['code']=item['imdb_id']
    if 'certification' in item: info['mpaa']=item['certification']
    if 'year' in item: info['year']=item['year']
    if 'season' in item: info['season']=item['season']
    if 'episode' in item: info['episode']=item['episode']
    if 'number' in item: info['episode']=item['number']
    if 'genres' in item: info['genre']=', '.join(item['genres'])
    if 'network' in item: info['studio']=item['network']
    if 'first_aired' in item: info['aired']=info['premiered']=time.strftime('%Y-%m-%d', time.localtime(item['first_aired']))
    if 'released' in item: info['premiered']=time.strftime('%Y-%m-%d', time.localtime(item['released']))
    if 'status' in item: info['status']=item['status']
    if 'tagline' in item: info['tagline']=item['tagline']
    if 'plays' in item and item['plays']: info['playcount']=item['plays']

    # override item params with show info if it exists
    if 'certification' in show: info['mpaa']=show['certification']
    if 'year' in show: info['year']=show['year']
    if 'imdb_id' in show: info['code']=show['imdb_id']
    if 'runtime' in show: info['duration']=show['runtime']
    if 'title' in show: info['tvshowtitle']=show['title']
    if 'people' in show: info['cast']=[actor['name'] for actor in show['people']['actors'] if actor['name']]
    if 'people' in show: info['castandrole']=['%s as %s' % (actor['name'],actor['character']) for actor in show['people']['actors'] if actor['name'] and actor['character']]
    return info
    
def get_section_params(section):
    section_params={}
    section_params['section']=section
    if section==SECTIONS.TV:
        set_view('tvshows')
        section_params['next_mode']=MODES.SEASONS
        section_params['folder']=True
        section_params['video_type']=VIDEO_TYPES.TVSHOW
    else:
        set_view('movies')
        section_params['next_mode']=MODES.GET_SOURCES
        section_params['folder']=ADDON.get_setting('source-win')=='Directory'
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

def filter_hosters(hosters):
    filtered_hosters=[]
    for host in hosters:
        for key, _ in SORT_FIELDS:
            if key in host and host[key] is None:
                break
        else:
            filtered_hosters.append(host)
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
                item_sort_key.append(sign*SORT_KEYS[field][value])
            else: # assume all unlisted values sort as worst
                item_sort_key.append(sign*-1)
        else:
            if item[field] is None:
                item_sort_key.append(sign*-1)
            else:
                item_sort_key.append(sign*item[field])
    #print 'item: %s sort_key: %s' % (item, item_sort_key)
    return tuple(item_sort_key)

def make_source_sort_key():
    sso=ADDON.get_setting('source_sort_order')
    sort_key={}
    i=0
    if sso:
        sources = sso.split('|')
        sort_key={}
        for i,source in enumerate(sources):
            sort_key[source]=-i
        
    scrapers = relevant_scrapers(include_disabled=True)
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

def parallel_get_sources(q, cls, video_type, title, year, season, episode):
    scraper_instance=cls(int(ADDON.get_setting('source_timeout')))
    if P_MODE == P_MODES.THREADS:
        worker=threading.current_thread()
    elif P_MODE == P_MODES.PROCESSES:
        worker=multiprocessing.current_process()
        
    log_utils.log('Getting %s sources using %s' % (cls.get_name(), worker), xbmc.LOGDEBUG)
    hosters=scraper_instance.get_sources(video_type, title, year, season, episode)
    log_utils.log('%s returned %s sources from %s' % (cls.get_name(), len(hosters), worker), xbmc.LOGDEBUG)
    q.put(hosters)

def parallel_get_url(q, cls, video_type, title, year, season, episode):
    scraper_instance=cls(int(ADDON.get_setting('source_timeout')))
    if P_MODE == P_MODES.THREADS:
        worker=threading.current_thread()
    elif P_MODE == P_MODES.PROCESSES:
        worker=multiprocessing.current_process()
        
    log_utils.log('Getting %s url using %s' % (cls.get_name(), worker), xbmc.LOGDEBUG)
    url=scraper_instance.get_url(video_type, title, year, season, episode)
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
    except TypeError:
        last_run=datetime.datetime(*(time.strptime(last_run_string, '%Y-%m-%d %H:%M:%S.%f')[0:6]))
    interval=datetime.timedelta(hours=float(ADDON.get_setting(task+'-interval')))
    return (last_run+interval)

def url_exists(video_type, title, year, season='', episode=''):
    """
    check each source for a url for this video; return True as soon as one is found. If none are found, return False
    """
    max_timeout = int(ADDON.get_setting('source_timeout'))
    log_utils.log('Checking for Url Existence: |%s|%s|%s|%s|%s|' % (video_type, title, year, season, episode), xbmc.LOGDEBUG)
    for cls in relevant_scrapers(video_type):
        scraper_instance=cls(max_timeout)
        url = scraper_instance.get_url(video_type, title, year, season, episode)
        if url:
            log_utils.log('Found url for |%s|%s|%s|%s|%s| @ %s: %s' % (video_type, title, year, season, episode, cls.get_name(), url), xbmc.LOGDEBUG)
            return True

    log_utils.log('No url found for: |%s|%s|%s|%s|%s|' % (video_type, title, year, season, episode))
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
    return '|%s|' % (name) not in ADDON.get_setting('disabled_scrapers')

def enable_scraper(name):
    if not scraper_enabled(name):
        disabled=ADDON.get_setting('disabled_scrapers')
        pattern = '|%s|' % (name)
        pieces = disabled.split(pattern)
        disabled='|'.join(pieces)
        if disabled=='|': disabled=''
        ADDON.set_setting('disabled_scrapers', disabled)

def disable_scraper(name):
    if scraper_enabled(name):
        disabled=ADDON.get_setting('disabled_scrapers')
        if not disabled:
            disabled = '|%s|' % (name)
        else:
            disabled = '%s%s|' % (disabled, name)
        ADDON.set_setting('disabled_scrapers', disabled)

def set_view(content):
    # set content type so library shows more views and info
    if content:
        xbmcplugin.setContent(int(sys.argv[1]), content)

    # set sort methods - probably we don't need all of them
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

def valid_account():
    username=ADDON.get_setting('username')
    password=ADDON.get_setting('password')
    last_hash=ADDON.get_setting('last_hash')
    cur_hash = md5.new(username+password).hexdigest()
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