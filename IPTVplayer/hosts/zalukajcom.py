﻿# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.dToolsSet.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.icomponents.ihost import CHostBase, CBaseHostClass, CDisplayListItem, ArticleContent, RetHost, CUrlItem
from Plugins.Extensions.IPTVPlayer.dToolsSet.iptvtools import CSelOneLink, printDBG, printExc, CSearchHistoryHelper, GetLogoDir, GetCookieDir, byteify, rm
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.itools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
###################################################

###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigInteger, ConfigSelection, ConfigYesNo, ConfigText, getConfigListEntry
from Tools.Directories import fileExists
from datetime import timedelta
from binascii import hexlify
import re
import urllib
import time
import random
try:    import simplejson as json
except Exception: import json
###################################################


###################################################
# E2 GUI COMMPONENTS 
###################################################
from Plugins.Extensions.IPTVPlayer.icomponents.asynccall import iptv_execute, MainSessionWrapper
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.zalukajtv_filmssort    = ConfigSelection(default = "ostatnio-dodane", choices = [("ostatnio-dodane", "ostatnio dodane"), ("ostatnio-ogladane", "ostatnio oglądane"), ("odslon", "odsłon"), ("ulubione", "ulubione"), ("oceny", "oceny"), ("mobilne", "mobilne")]) 
config.plugins.iptvplayer.zalukajtvPREMIUM       = ConfigYesNo(default = False)
config.plugins.iptvplayer.zalukajtv_login        = ConfigText(default = "", fixed_size = False)
config.plugins.iptvplayer.zalukajtv_password     = ConfigText(default = "", fixed_size = False)
config.plugins.iptvplayer.zalukajtv_proxy        = ConfigSelection(default = "None", choices = [("None",     _("None")),
                                                                                                ("proxy_1",  _("Alternative proxy server (1)")),
                                                                                                ("proxy_2",  _("Alternative proxy server (2)"))])
def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry("Sortuj filmy: ", config.plugins.iptvplayer.zalukajtv_filmssort))
    optionList.append(getConfigListEntry("Zaloguj:", config.plugins.iptvplayer.zalukajtvPREMIUM))
    if config.plugins.iptvplayer.zalukajtvPREMIUM.value:
        optionList.append(getConfigListEntry("  " + _("login") + ":", config.plugins.iptvplayer.zalukajtv_login))
        optionList.append(getConfigListEntry("  " + _("hasło") + ":", config.plugins.iptvplayer.zalukajtv_password))
    optionList.append(getConfigListEntry(_("Use proxy server:"),      config.plugins.iptvplayer.zalukajtv_proxy))
    return optionList
###################################################

def gettytul():
    return 'http://zalukaj.com/'

class ZalukajCOM(CBaseHostClass):
    USER_AGENT = 'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.2.18) Gecko/20110621 Mandriva Linux/1.9.2.18-0.1mdv2010.2 (2010.2) Firefox/3.6.18'
    HEADER = {'User-Agent': USER_AGENT, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}
    AJAX_HEADER = dict(HEADER)
    AJAX_HEADER.update( {'X-Requested-With': 'XMLHttpRequest', 'Connection': 'keep-alive', 'Pragma': 'no-cache', 'Cache-Control': 'no-cache'} )
    
    DOMAIN     = 'zalukaj.com'
    MAIN_URL   = 'https://' + DOMAIN + '/'
    FILMS_URL  = MAIN_URL + '/gatunek,%d/%s,%s,strona-%d'
    SEARCH_URL = MAIN_URL + '/szukaj'
    LOGIN_URL  = MAIN_URL + '/account.php'
    DEFAULT_ICON_URL = 'http://www.userlogos.org/files/logos/8596_famecky/zalukaj.png'
    MAIN_CAT_TAB = [{'category':'films_sub_menu', 'title':"Filmy",   'url': ''},
                    {'category':'series_sub_menu','title':"Seriale", 'url': MAIN_URL},
                    {'category':'search',         'title':"Szukaj filmu", 'search_item':True},
                    {'category':'search_history', 'title':_('Search history')} ]
                    
    FILMS_SUB_MENU = [{ 'category':'films_category', 'title':'Kategorie',        'url':MAIN_URL },
                      { 'category':'films_list',     'title':'Ostatnio oglądane', 'url':MAIN_URL + '/cache/lastseen.html' },
                      { 'category':'films_list',     'title':'Ostatnio dodane',   'url':MAIN_URL + '/cache/lastadded.html'},
                      { 'category':'films_popular',  'title':'Najpopularniejsze', 'url':'' } ]
                    
    FILMS_POPULAR = [{ 'category':'films_list', 'title':'Wczoraj',        'url':MAIN_URL + '/cache/wyswietlenia-wczoraj.html' },
                     { 'category':'films_list', 'title':'Ostatnie 7 dni', 'url':MAIN_URL + '/cache/wyswietlenia-tydzien.html' },
                     { 'category':'films_list', 'title':'W tym miesiącu', 'url':MAIN_URL + '/cache/wyswietlenia-miesiac.html'} ]
                     
    SERIES_SUB_MENU = [{ 'category':'series_list',   'title':'Lista',     'url':MAIN_URL },
                       { 'category':'series_updated','title':'Ostatnio zaktualizowane', 'url':MAIN_URL + '/seriale' } ]
                    
    LANGS_TAB = [{ 'title':'Wszystkie',     'lang':'wszystkie'      },
                 { 'title':'Z lektorem',    'lang':'tlumaczone'     },
                 { 'title':'Napisy pl',     'lang':'napisy-pl'      },
                 { 'title':'Nietłumaczone', 'lang':'nie-tlumaczone' } ]
     
    
    def __init__(self):
        printDBG("ZalukajCOM.__init__")
        CBaseHostClass.__init__(self, {'history':'ZalukajCOM', 'cookie':'zalukajtv.cookie', 'min_py_ver':(2,7,9)})
        self.loggedIn = None
        self.login    = ''
        self.password = ''
        self.msg = ''
        
    def _getPage(self, url, http_params_base={}, params=None, loggedIn=None):
        if None == loggedIn: loggedIn=self.loggedIn
        HEADER = ZalukajCOM.HEADER
        if loggedIn: http_params = {'header': HEADER, 'use_cookie': True, 'save_cookie': True, 'load_cookie': True, 'cookiefile': self.COOKIE_FILE}
        else: http_params = {'header': HEADER}
        http_params.update(http_params_base)
        return self.getPage(url, http_params, params)
        
    def getPage(self, url, addParams = {}, post_data = None):
        HTTP_HEADER= dict(self.HEADER)
        addParams = dict(addParams)
        addParams.update({'header':HTTP_HEADER})
            
        proxy = config.plugins.iptvplayer.zalukajtv_proxy.value
        if proxy != 'None':
            if proxy == 'proxy_1':
                proxy = config.plugins.iptvplayer.alternative_proxy1.value
            else:
                proxy = config.plugins.iptvplayer.alternative_proxy2.value
            addParams = dict(addParams)
            addParams.update({'http_proxy':proxy})
        
        sts, data = self.cm.getPage(url, addParams, post_data)
        if sts and None == data:
            sts = False
        if sts and 'Duze obciazenie!' in data:
            SetIPTVPlayerLastHostError(self.cleanHtmlStr(re.compile('''<script.+?</script>''', re.DOTALL).sub("", data)))
        return sts, data
        
    def getFullIconUrl(self, url):
        url = self.getFullUrl(url)
        proxy = config.plugins.iptvplayer.zalukajtv_proxy.value
        if proxy != 'None':
            if proxy == 'proxy_1':
                proxy = config.plugins.iptvplayer.alternative_proxy1.value
            else:
                proxy = config.plugins.iptvplayer.alternative_proxy2.value
            url = strwithmeta(url, {'iptv_http_proxy':proxy})
        return url
            
    def _listLeftTable(self, cItem, category, m1, m2, sp):
        printDBG("ZalukajCOM.listLeftGrid")
        sts, data = self._getPage(cItem['url'])
        if not sts: return
        printDBG(data)
        data = self.cm.ph.getDataBeetwenMarkers(data, m1, m2, False)[1]
        data = data.split(sp)
        if len(data): del data[-1]
        for item in data:
            params = dict(cItem)
            url    = self.getFullUrl( self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"', 1)[0] )
            if self.DOMAIN not in url: continue
            params.update({'category':category, 'title':self.cleanHtmlStr( item ), 'url':url})
            self.addDir(params)
        
    def listFilmsCategories(self, cItem, category):
        printDBG("ZalukajCOM.listFilmsCategories")
        self._listLeftTable(cItem, category, '<table id="one" cellpadding="0" cellspacing="3">', '</table>', '</td>')
        
    def listSeries(self, cItem, category):
        printDBG("ZalukajCOM.listFilmsCategories")
        self._listLeftTable(cItem, category, '<table id="main_menu" cellpadding="0" cellspacing="3">', '</table>', '</td>')
        
    def listFilms(self, cItem):
        printDBG("ZalukajCOM.listFilms")
        url      = cItem['url']
        page = cItem.get('page', 1)
        nextPage = False
        extract  = False
        try:
            cat  = int(url.split('/')[-1])
            sort = config.plugins.iptvplayer.zalukajtv_filmssort.value
            url  = ZalukajCOM.FILMS_URL % (cat, sort, cItem['lang'], page)
            extract = True
        except Exception: pass
        sts, data = self._getPage(url, {}, cItem.get('post_data', None))
        #self.cm.ph.writeToFile("/home/sulge/zalukaj.html", data)
        if not sts: return
        sp = '<div class="tivief4">'
        if extract:
            if self.cm.ph.getSearchGroups(data, 'strona\-(%d)[^0-9]' % (page+1))[0] != '':
                nextPage = True
            m2 = '<div class="categories_page">' 
            if m2 not in data: m2 = '<div class="doln">'
            data = self.cm.ph.getDataBeetwenMarkers(data, sp, m2, True)[1]
        data = data.split(sp)
        if len(data): del data[0]
        for item in data:
            year = self.cleanHtmlStr( self.cm.ph.getDataBeetwenMarkers(item, '<p>', '</p>', False)[1] )
            desc = self.cleanHtmlStr( self.cm.ph.getDataBeetwenMarkers(item, '</h3>', '</div>', False)[1] )
            more = self.cleanHtmlStr( self.cm.ph.getDataBeetwenMarkers(item, '<p class="few_more">', '</p>', False)[1] )
            desc = '%s | %s | %s |' % (year, more, desc)
            icon = self.getFullUrl( self.cm.ph.getDataBeetwenMarkers(item, 'background-image:url(', ')', False)[1] )
            if '' == icon: icon = self.getFullUrl( self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"', 1)[0] )
            url  = self.getFullUrl( self.cm.ph.getSearchGroups(item, '<a href="([^"]+?)"', 1)[0] )
            title = self.cleanHtmlStr( self.cm.ph.getSearchGroups(item, 'title="([^"]+?)"', 1)[0] ) 
            title2 = self.cleanHtmlStr( self.cm.ph.getDataBeetwenMarkers(item, '<h3>', '</h3>', False)[1] ) 
            if len(title) < len(title2): title = title2
            if '' != url: self.addVideo({'title':title, 'url':url, 'desc':desc, 'icon':icon})
        if nextPage: 
            params = dict(cItem)
            params.update({'title':_('Następna strona'), 'page':page+1})
            self.addDir(params)
            
    def listUpdatedSeries(self, cItem, category):
        printDBG("ZalukajCOM.listUpdatedSeries")
        sts, data = self._getPage(cItem['url'])
        if not sts: return
        sp = '<div class="latest tooltip">'
        m2 = '<div class="doln">'
        data = self.cm.ph.getDataBeetwenMarkers(data, sp, m2, True)[1]
        data = data.split(sp)
        if len(data): del data[0]
        for item in data:
            icon  = self.getFullUrl( self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"', 1)[0] )
            url   = self.getFullUrl( self.cm.ph.getSearchGroups(item, '<a href="([^"]+?)"', 1)[0] )
            title = self.cleanHtmlStr( self.cm.ph.getDataBeetwenMarkers(item, '<div class="latest_title">', '</div>', False)[1] ) 
            desc  = self.cleanHtmlStr( self.cm.ph.getDataBeetwenMarkers(item, '<div class="latest_info">', '</div>', False)[1] )
            if '' == url: continue
            params = dict(cItem)
            params.update({'category':category, 'title':title, 'url':url, 'desc':desc, 'icon':icon})
            self.addDir(params)
            
    def _listSeriesBase(self, cItem, category, m1, m2, sp):
        printDBG("ZalukajCOM._listSeriesBase")
        sts, data = self._getPage(cItem['url'])
        if not sts: return

        data = self.cm.ph.getDataBeetwenMarkers(data, m1, m2, True)[1]
        icon  = self.getFullUrl( self.cm.ph.getSearchGroups(data, 'src="([^"]+?)"', 1)[0] )
        if '' == icon: icon = cItem.get('icon', '')
        data = data.split(sp)
        if len(data): del data[-1]
        for item in data:
            url   = self.getFullUrl( self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"', 1)[0] )
            title = self.cleanHtmlStr( item ) 
            if '' == url: continue
            params = dict(cItem)
            params.update({'category':category, 'title':title, 'url':url, 'icon':icon})
            if 'video' == category: self.addVideo(params)
            else: self.addDir(params)
                
    def listSeriesSeasons(self, cItem, category):
        printDBG("ZalukajCOM.listSeriesSeasons")
        self._listSeriesBase(cItem, category, '<div id="sezony" align="center">', '<div class="doln2">', '</div>')
        if 1 == len(self.currList):
            newItem = self.currList[0]
            self.currList = []
            self.listSeriesEpisodes(newItem)
        
    def listSeriesEpisodes(self, cItem):
        printDBG("ZalukajCOM.listSeriesEpisodes")
        self._listSeriesBase(cItem, 'video', '<div id="odcinkicat">', '<div class="doln2">', '</div>')
        
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("ZalukajCOM.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        #searchPattern = urllib.quote_plus(searchPattern)
        post_data = {'searchinput':searchPattern}
        params = {'name':'category', 'category':'films_list', 'url': ZalukajCOM.SEARCH_URL, 'post_data':post_data}
        self.listFilms(params)
    
    def getLinksForVideo(self, cItem):
        printDBG("ZalukajCOM.getLinksForVideo url[%s]" % cItem['url'])
        self.tryTologin()
        
        if self.loggedIn: tries= [True, False]
        else: tries= [False]
        urlTab = []
        for loggedIn in tries:
            url = cItem['url']
            sts, data = self._getPage(url, loggedIn=loggedIn)
            if not sts: continue
            url = self.getFullUrl( self.cm.ph.getSearchGroups(data, '"([^"]+?player.php[^"]+?)"', 1)[0] )
            if '' == url:
                printDBG( 'No player.php in data')
                data = self.cm.ph.getDataBeetwenMarkers(data, 'Oglądaj Film Online', '<div class="doln">', False)[1]
                url = self.getFullUrl( self.cm.ph.getSearchGroups(data, 'href="([^"]+?)"[^>]*?target', 1)[0] )
                urlTab.extend(self.up.getVideoLinkExt(url))
                continue 
            sts, data = self._getPage(url, loggedIn=loggedIn)
            if not sts: continue
            url = self.getFullUrl(self.cm.ph.getSearchGroups(data, '<a href="([^"]+?)"', 1)[0])
            if '' == url:
                printDBG( 'No href in data[%s]' % '')
                continue
                
            sts, data = self._getPage(url, loggedIn=loggedIn)
            if not sts: continue
            
            # First check for premium link
            premium = False
            premiumLinks = self.cm.ph.getSearchGroups(data, '"bitrates"\t?\:\t?(\[[^]]+?\])', 1)[0]
            if premiumLinks != '':
                printDBG("New premium premiumLinks: [%s]" % premiumLinks)
                try:
                    premiumLinks = byteify( json.loads(premiumLinks) )
                    for pItem in premiumLinks:
                        urlTab.append({'name':'zalukaj.tv premium ' + pItem.get('label', ''), 'url':pItem['url']})
                        premium = True
                except Exception:
                    printExc()
            
            if not premium:
                url = self.cm.ph.getSearchGroups(data, "url:'([^']+?)'", 1)[0]
                printDBG("Old premium url: [%s]" % url)
                if url.startswith('http'):
                    urlTab.append({'name':'zalukaj.tv premium ', 'url':url})
                    premium = True
                    
            if not premium:
                printDBG( 'No premium link data[%s]' % data)
                tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, '<source', '>', False, False)
                for item in tmp:
                    if 'video/mp4' in item or '.mp4' in item:
                        label = self.cm.ph.getSearchGroups(item, '''label=['"]([^"^']+?)['"]''')[0]
                        res = self.cm.ph.getSearchGroups(item, '''res=['"]([^"^']+?)['"]''')[0]
                        if label == '': label = res
                        url = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0]
                        if url.startswith('//'): url = 'http:' + url
                        if not self.cm.isValidUrl(url): continue
                        urlTab.append({'name':'zalukaj.tv premium ' + label, 'url':strwithmeta(url, {'Referer':cItem['url']})})
                        premium = True
            if not premium:
                url = self.getFullUrl( self.cm.ph.getSearchGroups(data, 'iframe src="([^"]+?)" width=', 1)[0] )
                if self.cm.isValidUrl(url):
                    urlTab.extend(self.up.getVideoLinkExt(url))
                # premium link should be checked at first, so if we have free link here break
                if len(urlTab):
                    break
        return urlTab
        
    def tryTologin(self):
        printDBG('tryTologin start')
        
        config.plugins.iptvplayer.zalukajtv_login   
        config.plugins.iptvplayer.zalukajtv_password
        
        if None == self.loggedIn or self.login != config.plugins.iptvplayer.zalukajtv_login.value or\
            self.password != config.plugins.iptvplayer.zalukajtv_password.value:
        
            self.login = config.plugins.iptvplayer.zalukajtv_login.value
            self.password = config.plugins.iptvplayer.zalukajtv_password.value
            
            rm(self.COOKIE_FILE)
            
            self.loggedIn = False
            self.msg = ''
            
            if '' == self.login.strip() or '' == self.password.strip():
                return False
            
            rm(self.COOKIE_FILE)
            sts, msg = False, 'Problem z zalogowaniem użytkownika \n"%s".' % self.login
            post_data = {'login': self.login, 'password': self.password}
            sts, data  = self._getPage(ZalukajCOM.LOGIN_URL, params=post_data, loggedIn=True)
            if sts:
                printDBG( 'Host getInitList: chyba zalogowano do premium...' )
                sts, data = self._getPage(url=self.getFullUrl('/libs/ajax/login.php?login=1'), loggedIn=True)
                
                if sts: 
                    sts, data2 = self._getPage(self.getFullUrl('/libs/ajax/login.php?login=1'), loggedIn=True)

                if sts:
                    printDBG(data)
                    sts,tmp = self.cm.ph.getDataBeetwenMarkers(data, '<p>Typ Konta:', '</p>', False)
                    if sts: 
                        tmp = tmp.replace('(kliknij by oglądać bez limitów)', '')
                        msg = 'Zostałeś poprawnie zalogowany.' + '\nTyp Konta: '+self.cleanHtmlStr(tmp)
                        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<p>Zebrane Punkty:', '</p>', False)[1].replace('&raquo; Wymień na VIP &laquo;', '')
                        if '' != tmp: msg += '\nZebrane Punkty: '+self.cleanHtmlStr(tmp)
                        self.loggedIn = True
            
            if not self.loggedIn: self.sessionEx.open(MessageBox, msg, type = MessageBox.TYPE_INFO, timeout = 10 )
            else: self.msg = msg.replace('\n', '[/br]')
        
        return self.loggedIn
    
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('ZalukajCOM.handleService start')
        
        self.tryTologin()

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name     = self.currItem.get("name", None)
        category = self.currItem.get("category", '')
        printDBG( "ZalukajCOM.handleService: ---------> name[%s], category[%s] " % (name, category) )
        searchPattern = self.currItem.get("search_pattern", searchPattern)
        self.currList = [] 

        if None == name:
            self.listsTab(ZalukajCOM.MAIN_CAT_TAB, {'name':'category', 'desc':self.msg})
    #FILMS
        elif 'films_sub_menu' == category:
            self.listsTab(ZalukajCOM.FILMS_SUB_MENU, self.currItem)
        elif 'films_popular' == category:
            self.listsTab(ZalukajCOM.FILMS_POPULAR, self.currItem) 
        elif 'films_category' == category:
            self.listFilmsCategories(self.currItem, 'add_lang')
    #LANGS
        elif 'add_lang' == category:
            newItem = dict(self.currItem)
            newItem.update({'category':'films_list'})
            self.listsTab(ZalukajCOM.LANGS_TAB, newItem)
    #LIST FILMS 
        elif 'films_list' == category:
            self.listFilms(self.currItem)
    #SERIES
        elif 'series_sub_menu' == category:
            self.listsTab(ZalukajCOM.SERIES_SUB_MENU, self.currItem)
        elif 'series_list' == category:
            self.listSeries(self.currItem, 'series_seasons')
        elif 'series_updated' == category:
            self.listUpdatedSeries(self.currItem, 'series_episodes')
        elif 'series_seasons' == category:
            self.listSeriesSeasons(self.currItem, 'series_episodes')
        elif 'series_episodes' == category:
            self.listSeriesEpisodes(self.currItem)
    #WYSZUKAJ
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item':False, 'name':'category'}) 
            self.listSearchResult(cItem, searchPattern, searchType)
    #HISTORIA WYSZUKIWANIA
        elif category == "search_history":
            self.listsHistory({'name':'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, ZalukajCOM(), True)