{
    'name': 'Project Management (Custom)',
    'version': '19.0.1.0.73',
    'summary': 'Manage projects with multi-tier approvals, role dashboards, team tracking, and performance leaderboard',
    'author': 'Custom',
    'category': 'Project',
    'depends': ['base', 'hr', 'mail', 'web'],
    'data': [
        'security/project_security.xml',
        'security/ir.model.access.csv',
        'security/project_rules.xml',
        'views/dashboard_views.xml',
        'views/project_approval_views.xml',
        'views/project_team_views.xml',
        'views/project_scope_views.xml',
        'views/import_wizard_views.xml',
        'views/project_review_views.xml',
        'views/project_manage_views.xml',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'project_manage/static/src/components/dashboard/**/*',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
