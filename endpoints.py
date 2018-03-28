from typing import List, Dict

URLS: List[str] = [
    '/metrics/edited-pages/aggregate/{project}/{editor-type}/{page-type}/{activity-level}/{granularity}/{start}/{end}',
    '/metrics/edits/aggregate/{project}/{editor-type}/{page-type}/{granularity}/{start}/{end}',
    '/metrics/edited-pages/new/{project}/{editor-type}/{page-type}/{granularity}/{start}/{end}',
    '/metrics/editors/aggregate/{project}/{editor-type}/{page-type}/{activity-level}/{granularity}/{start}/{end}',
    '/metrics/registered-users/new/{project}/{granularity}/{start}/{end}',
    '/metrics/bytes-difference/net/aggregate/{project}/{editor-type}/{page-type}/{granularity}/{start}/{end}',
    '/metrics/bytes-difference/absolute/aggregate/{project}/{editor-type}/{page-type}/{granularity}/{start}/{end}',
    '/metrics/unique-devices/{project}/{access-site}/{granularity}/{start}/{end}',
    '/metrics/pageviews/aggregate/{project}/{access}/{agent}/{granularity}/{start}/{end}',
    '/metrics/edited-pages/top-by-edits/{project}/{editor-type}/{page-type}/{granularity}/{start}/{end}',
]

defaultCombinations: Dict[str, str] = {
    'editorType': 'anonymous,group-bot,name-bot,user'.split(','),
    'pageType': 'content,non-content'.split(','),
    'accessSite': 'desktop-site,mobile-site'.split(','),
    'access': 'desktop,mobile-app,mobile-web'.split(','),
    'agent': 'user,spider'.split(','),
    'activityLevel': 'all-activity-levels'.split(',')
}

BASE_URL: str = 'https://wikimedia.org/api/rest_v1'
