# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.dToolsSet.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError, GetIPTVSleep
from Plugins.Extensions.IPTVPlayer.icomponents.ihost import CHostBase, CBaseHostClass, CDisplayListItem, RetHost, CUrlItem, ArticleContent
from Plugins.Extensions.IPTVPlayer.dToolsSet.iptvtools import printDBG, printExc, GetCookieDir, byteify, rm
from Plugins.Extensions.IPTVPlayer.itools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.icomponents.asynccall import iptv_js_execute
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
###################################################

###################################################
# FOREIGN import
###################################################
import time
import re
import urllib
import string
import random
import base64
from copy import deepcopy
from urlparse import urlparse
from hashlib import md5
try:    import json
except Exception: import simplejson as json
from Components.config import config, ConfigSelection, ConfigYesNo, ConfigText, getConfigListEntry
###################################################


###################################################
# E2 GUI COMMPONENTS 
###################################################
from Plugins.Extensions.IPTVPlayer.icomponents.asynccall import MainSessionWrapper
###################################################

def gettytul():
    return 'http://3sk.tv/'

class C3skTv(CBaseHostClass):
 
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'3sk.tv', 'cookie':'3sk.tv.cookie', 'cookie_type':'MozillaCookieJar', 'min_py_ver':(2,7,9)})
        self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        
        self.DEFAULT_ICON_URL = 'http://www.3sk.tv/images/logo-footer.png'
        self.HEADER = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0', 'DNT':'1', 'Accept':'text/html', 'Accept-Encoding':'gzip, deflate'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update( {'X-Requested-With': 'XMLHttpRequest', 'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8', 'Accept':'*/*'} )
        self.MAIN_URL = None
        self.cacheLinks = {}
        self.seasonsCache = {}
        self.defaultParams = {'header':self.HEADER, 'with_metadata':True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        
    def getPage(self, url, addParams = {}, post_data = None):
        if addParams == {}: addParams = dict(self.defaultParams)
        baseUrl = self.cm.iriToUri(url)
        return self.cm.getPage(baseUrl, addParams, post_data)
        
    def selectDomain(self):
        domain = 'http://www.3sk.tv/'
        addParams = dict(self.defaultParams)
        addParams['with_metadata'] = True
        
        sts, data = self.getPage(domain, addParams)
        if sts: self.MAIN_URL = self.cm.getBaseUrl(data.meta['url'])
        else: self.MAIN_URL = domain
    
    def listMainMenu(self, cItem):
        printDBG("C3skTv.listMainMenu")
        sts, data = self.getPage(self.getMainUrl())
        if sts:
            data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'zone_2'), ('<div', '>', 'banner2'))[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
            for item in data:
                nextCategory = ''
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0])
                if url == '' or 'pdep43.' in url: continue
                
                parsedUri = urlparse(url)
                if parsedUri.path == '' and self.cm.isValidUrl(url):
                    url += '/'
                    parsedUri = urlparse(url)
                
                if 'forumdisplay.php' in url or (parsedUri.path == '/vb' and parsedUri.query == ''):
                    nextCategory = 'list_threads'
                elif '/pdep' in url or (parsedUri.path == '/' and parsedUri.query == ''):
                    nextCategory = 'list_items'
                title = self.cleanHtmlStr(item)
                printDBG(">>>>>>>>>>>>>>>>> title[%s] url[%s] path[%s] query[%s]" % (title, url, parsedUri.path, parsedUri.query ))
                params = dict(cItem)
                params.update({'good_for_fav':False, 'category':nextCategory, 'title':title, 'url':url})
                self.addDir(params)
        #self.listsTab(self.MAIN_CAT_TAB, cItem)
        
    def listItems(self, cItem):
        printDBG("C3skTv.listItems")
        
        page = cItem.get('page', 1)
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        
        currentUrl = data.meta['url']
        
        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'pagination'), ('</table', '>'))[1]
        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(nextPage, '''\shref=['"]([^'^"]*?p%s\.html)['"]''' % (page + 1))[0], currentUrl)
        
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', '"article"'), ('</div', '>'))
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0], currentUrl)
            if url == currentUrl: continue
            
            if 'forumdisplay.php' in url:
                nextCategory = 'list_threads'
            elif 'showthread.php' in url:
                nextCategory = 'list_thread'
            else:
                continue
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^'^"]+?)['"]''')[0], currentUrl)
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<a', '</a>')[1])
            desc  = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<p', '</p>')[1])
            
            params = dict(cItem)
            params.update({'good_for_fav':True, 'category':nextCategory, 'title':title, 'url':url, 'icon':icon, 'desc':desc})
            self.addDir(params)
            
        if nextPage != '':
            params = dict(cItem)
            params.update({'good_for_fav':False, 'title':_('Next page'), 'url':nextPage, 'page':page + 1})
            self.addDir(params)
            
    def listThreads(self, cItem, nextCategory):
        printDBG("C3skTv.listThreads")
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        
        currentUrl = data.meta['url']
        
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<tr', '</tr>')
        for item in data:
            if 'vbmenu_option' in item: continue
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0], currentUrl)
            if url == currentUrl: continue
            #printDBG("++++++++ [%s]" % url)
            if 'forumdisplay.php' in url:
                nextCategory = 'list_threads'
            elif 'showthread.php' in url:
                nextCategory = 'list_thread'
            else:
                continue
            title = self.cleanHtmlStr(item)
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^'^"]+?)['"]''')[0], currentUrl)
            
            params = dict(cItem)
            params.update({'good_for_fav':True, 'category':nextCategory, 'title':title, 'url':url, 'icon':icon})
            self.addDir(params)
            
    def listThread(self, cItem):
        printDBG("C3skTv.listThread")
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        
        currentUrl = data.meta['url']
        domain = self.up.getDomain(currentUrl)
        
        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'post_message_'), ('<script', '>'), False)[1]
        data = re.compile('''</?br[^>]*?>''').split(data)
        
        for tmp in data:
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<font', '</a>')
            for item in tmp:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0], currentUrl)
                printDBG(">>>>>>>>>>>>>>> " + url)
                tmp = self.cm.getBaseUrl(url)
                if domain in tmp and '/vid/' not in url and '/show/' not in url: continue
                title = self.cleanHtmlStr(item)
                params = dict(cItem)
                params.update({'good_for_fav':False, 'title':'%s - %s' % (cItem['title'], title), 'url':url})
                self.addVideo(params)
    
    def getLinksForVideo(self, cItem):
        printDBG("C3skTv.getLinksForVideo [%s]" % cItem)
        videoUrl = cItem['url']
        urlTab = []
        
        if 1 == self.up.checkHostSupport(videoUrl): 
            return self.up.getVideoLinkExt(videoUrl)
        
        if cItem['url'] in self.cacheLinks:
            return self.cacheLinks[videoUrl]
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        
        currentUrl = data.meta['url']
            
        if '/vid/' in currentUrl:
            nameMap = {'1':"الاول", '2':"الثانى", '3':"الثالث", '4':"الرابع", '5':"الخامس", '6':"السادس", '7':"السابع", '8':"الثامن"}
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<iframe', '</iframe>', caseSensitive=False)
            for idx in range(len(data)):
                url = self.getFullUrl(self.cm.ph.getSearchGroups(data[idx], '''\ssrc=['"]([^"^']+?)['"]''', 1, True)[0], currentUrl)
                if url == '': continue
                name = str(idx+1)
                name = 'الجزء ' + nameMap.get(name, name)
                urlTab.append({'url':url, 'name':name, 'need_resolve':1})
        
        if len(urlTab):
            self.cacheLinks[videoUrl] = urlTab
        
        return urlTab
        
    def getVideoLinks(self, videoUrl):
        printDBG("C3skTv.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        
        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']
                        break
        
        return self.up.getVideoLinkExt(videoUrl)
        
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if self.MAIN_URL == None:
            rm(self.COOKIE_FILE)
            self.selectDomain()

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode     = self.currItem.get("mode", '')
        
        printDBG( "handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category) )
        self.currList = []
        
    #MAIN MENU
        if name == None:
            self.listMainMenu({'name':'category'})
        elif category == 'list_threads':
            self.listThreads(self.currItem, 'list_thread')
        elif category == 'list_thread':
            self.listThread(self.currItem)
        elif category == 'list_items':
            self.listItems(self.currItem)
        else:
            printExc()
        
        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, C3skTv(), True, [])
    