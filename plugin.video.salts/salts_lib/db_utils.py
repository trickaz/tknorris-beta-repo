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
import os
import time
import xbmc
import xbmcvfs
from addon.common.addon import Addon
import log_utils

def enum(**enums):
    return type('Enum', (), enums)

DB_TYPES= enum(MYSQL='mysql', SQLITE='sqlite')

_SALTS = Addon('plugin.video.salts')

class DB_Connection():
    def __init__(self):
        global db_lib
        self.dbname = _SALTS.get_setting('db_name')
        self.username = _SALTS.get_setting('db_user')
        self.password = _SALTS.get_setting('db_pass')
        self.address = _SALTS.get_setting('db_address')
        self.db=None
        
        if _SALTS.get_setting('use_remote_db') == 'true':
            if self.address is not None and self.username is not None \
            and self.password is not None and self.dbname is not None:
                import mysql.connector as db_lib
                log_utils.log('Loading MySQL as DB engine')
                self.db_type = DB_TYPES.MYSQL
            else:
                log_utils.log('MySQL is enabled but not setup correctly', xbmc.LOGERROR)
                raise ValueError('MySQL enabled but not setup correctly')
        else:
            try:
                from sqlite3 import dbapi2 as db_lib
                log_utils.log('Loading sqlite3 as DB engine')
            except:
                from pysqlite2 import dbapi2 as db_lib
                log_utils.log('pysqlite2 as DB engine')
            self.db_type = DB_TYPES.SQLITE
            db_dir = xbmc.translatePath("special://database")
            self.db_path = os.path.join(db_dir, 'saltscache.db')
        self.__connect_to_db()
    
    def flush_cache(self):
        sql = 'DELETE FROM url_cache'
        self.__execute(sql)

    # return the bookmark for the requested url or None if not found
    def get_bookmark(self,url):
        if not url: return None
        sql='SELECT resumepoint FROM new_bkmark where url=?'
        bookmark = self.__execute(sql, (url,))
        if bookmark:
            return bookmark[0][0]
        else:
            return None

    # get all bookmarks
    def get_bookmarks(self):
        sql='SELECT * FROM new_bkmark'
        bookmarks = self.__execute(sql)
        return bookmarks
    
    # return true if bookmark exists
    def bookmark_exists(self, url):
        return self.get_bookmark(url) != None
    
    def set_bookmark(self, url,offset):
        if not url: return
        sql = 'REPLACE INTO new_bkmark (url, resumepoint) VALUES(?,?)'
        self.__execute(sql, (url,offset))
        
    def clear_bookmark(self, url):
        if not url: return
        sql = 'DELETE FROM new_bkmark WHERE url=?'
        self.__execute(sql, (url,))
    
    def cache_url(self,url,body):
        now = time.time()
        sql = 'REPLACE INTO url_cache (url,response,timestamp) VALUES(?, ?, ?)'
        self.__execute(sql, (url, body, now))
    
    def get_cached_url(self, url, cache_limit=8):
        html=''
        now = time.time()
        limit = 60 * 60 * cache_limit
        sql = 'SELECT * FROM url_cache WHERE url = ?'
        rows=self.__execute(sql, (url,))
            
        if rows:
            created = float(rows[0][2])
            age = now - created
            if age < limit:
                html=rows[0][1]
        return html
    
    def add_other_list(self, section, username, slug):
        sql = 'REPLACE INTO other_lists (section, username, slug) VALUES (?, ?, ?)'
        self.__execute(sql, (section, username, slug))
        
    def delete_other_list(self, section, username, slug):
        sql = 'DELETE FROM other_lists WHERE section=? AND username=? and slug=?'
        self.__execute(sql, (section, username, slug))

    def get_other_lists(self, section):
        sql = 'SELECT username, slug FROM other_lists WHERE section=?'
        rows=self.__execute(sql, (section,))
        return rows

    def set_related_url(self, video_type, title, year, source, rel_url, season='', episode=''):
        sql = 'REPLACE INTO rel_url (video_type, title, year, season, episode, source, rel_url) VALUES (?, ?, ?, ?, ?, ?, ?)'
        self.__execute(sql, (video_type, title, year, season, episode, source, rel_url))
        
    def clear_related_url(self, video_type, title, year, source, season='', episode=''):
        sql = 'DELETE FROM rel_url WHERE video_type=? and title=? and year=? and source=?'
        params=[video_type, title, year,  source]
        if season and episode:
            sql += ' and season=? and episode=?'
            params += [season, episode]
        self.__execute(sql, params)

    def get_related_url(self, video_type, title, year, source, season='', episode=''):
        sql = 'SELECT rel_url FROM rel_url WHERE video_type=? and title=? and year=? and season=? and episode=? and source=?'
        rows=self.__execute(sql, (video_type, title, year, season, episode, source))
        return rows
                       
    def get_setting(self, setting):
        sql = 'SELECT value FROM db_info WHERE setting=?'
        rows=self.__execute(sql, (setting,))
        if rows:
            return rows[0][0]
    
    def set_setting(self, setting, value):
        sql = 'REPLACE INTO db_info (setting, value) VALUES (?, ?)'
        self.__execute(sql, (setting, value))
    
    def execute_sql(self, sql):
        self.__execute(sql)

    # intended to be a common method for creating a db from scratch
    def init_database(self):
        log_utils.log('Building SALTS Database', xbmc.LOGDEBUG)
        if self.db_type == DB_TYPES.MYSQL:
            self.__execute('CREATE TABLE IF NOT EXISTS url_cache (url VARCHAR(255) NOT NULL, response MEDIUMBLOB, timestamp TEXT, PRIMARY KEY(url))')
            self.__execute('CREATE TABLE IF NOT EXISTS db_info (setting VARCHAR(255) NOT NULL, value TEXT, PRIMARY KEY(setting))')
            self.__execute('CREATE TABLE IF NOT EXISTS rel_url \
            (video_type VARCHAR(15) NOT NULL, title VARCHAR(255) NOT NULL, year VARCHAR(4) NOT NULL, season VARCHAR(5) NOT NULL, episode VARCHAR(5) NOT NULL, source VARCHAR(50) NOT NULL, rel_url VARCHAR(255), \
            PRIMARY KEY(video_type, title, year, season, episode, source))')
            self.__execute('CREATE TABLE IF NOT EXISTS other_lists (section VARCHAR(10) NOT NULL, username VARCHAR(255) NOT NULL, slug VARCHAR(255) NOT NULL, PRIMARY KEY(section, username, slug))')
        else:
            self.__create_sqlite_db()
            self.__execute('CREATE TABLE IF NOT EXISTS url_cache (url VARCHAR(255) NOT NULL, response, timestamp, PRIMARY KEY(url))')
            self.__execute('CREATE TABLE IF NOT EXISTS db_info (setting VARCHAR(255), value TEXT, PRIMARY KEY(setting))')
            self.__execute('CREATE TABLE IF NOT EXISTS rel_url \
            (video_type TEXT NOT NULL, title TEXT NOT NULL, year TEXT NOT NULL, season TEXT NOT NULL, episode TEXT NOT NULL, source TEXT NOT NULL, rel_url TEXT, \
            PRIMARY KEY(video_type, title, year, season, episode, source))')
            self.__execute('CREATE TABLE IF NOT EXISTS other_lists (section TEXT NOT NULL, username TEXT NOT NULL, slug TEXT NOT NULL, PRIMARY KEY(section, username, slug))')
                
        sql = 'REPLACE INTO db_info (setting, value) VALUES(?,?)'
        self.__execute(sql, ('version', _SALTS.get_version()))

    def __table_exists(self, table):
        if self.db_type==DB_TYPES.MYSQL:
            sql='SHOW TABLES LIKE ?'
        else:
            sql='select name from sqlite_master where type="table" and name = ?'
        rows=self.__execute(sql, (table,))
        
        if not rows:
            return False
        else:
            return True
        
    def reset_db(self):
        if self.db_type==DB_TYPES.SQLITE:
            os.remove(self.db_path)
            self.db=None
            self.__connect_to_db()
            self.init_database()
            return True
        else:
            return False
    
    def __execute(self, sql, params=None):
        if params is None:
            params=[]
            
        rows=None
        sql=self.__format(sql)
        cur = self.db.cursor()
        #log_utils.log('Running: %s with %s' % (sql, params), xbmc.LOGDEBUG)
        cur.execute(sql, params)
        if sql[:6].upper() == 'SELECT' or sql[:4].upper() == 'SHOW':
            rows=cur.fetchall()
        cur.close()
        self.db.commit()
        return rows

    def __get_db_version(self):
        version=None
        try:
            sql = 'SELECT value FROM db_info WHERE setting="version"'
            rows=self.__execute(sql)
        except:
            return None
        
        if rows: 
            version=rows[0][0]
            
        return version
    
    def __create_sqlite_db(self):
        if not xbmcvfs.exists(os.path.dirname(self.db_path)): 
            try: xbmcvfs.mkdirs(os.path.dirname(self.db_path))
            except: os.mkdir(os.path.dirname(self.db_path))
    
    def __drop_all(self):
        if self.db_type==DB_TYPES.MYSQL:
            sql = 'show tables'
        else:
            sql = 'select name from sqlite_master where type="table"'
        rows=self.__execute(sql)
        db_objects = [row[0] for row in rows]
            
        for db_object in db_objects:
            sql = 'DROP TABLE IF EXISTS %s' % (db_object)
            self.__execute(sql)
            
    def __connect_to_db(self):
        if not self.db:
            if self.db_type == DB_TYPES.MYSQL:
                self.db = db_lib.connect(database=self.dbname, user=self.username, password=self.password, host=self.address, buffered=True)
            else:
                self.db = db_lib.connect(self.db_path)
                self.db.text_factory = str

    # apply formatting changes to make sql work with a particular db driver
    def __format(self, sql):
        if self.db_type ==DB_TYPES.MYSQL:
            sql = sql.replace('?', '%s')
            
        if self.db_type == DB_TYPES.SQLITE:
            if sql[:7]=='REPLACE':
                sql = 'INSERT OR ' + sql

        return sql
