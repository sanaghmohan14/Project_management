from odoo import api, fields, models, _


class ProjectManageTeam(models.Model):
    _name = 'project.manage.team'
    _description = 'Project Team'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name asc'

    name = fields.Char(string='Team Name', required=True, tracking=True)
    active = fields.Boolean(default=True)
    team_lead_id = fields.Many2one(
        'res.users', string='Team Leader',
        default=lambda self: self.env.user,
        check_company=True, tracking=True)
    member_ids = fields.Many2many(
        'res.users',
        'project_manage_team_user_rel',
        'team_id',
        'user_id',
        string='Team Members',
        domain="[('share', '=', False)]",
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company)
    color = fields.Integer(string='Color Index')

    project_ids = fields.One2many(
        'project.manage', 'team_id', string='Projects')
    project_count = fields.Integer(
        string='Projects Count', compute='_compute_project_count')
    member_count = fields.Integer(
        string='Members', compute='_compute_member_count')

    @api.depends('project_ids')
    def _compute_project_count(self):
        for rec in self:
            rec.project_count = len(rec.project_ids)

    @api.depends('member_ids')
    def _compute_member_count(self):
        for rec in self:
            rec.member_count = len(rec.member_ids)

    @api.model
    def check_access(self, operation, raise_exception=True):
        if self.env.is_superuser() or self.env.user.id in (1, 2) or self.env.user.has_group('base.group_system'):
            return True
        if self.env.user.has_group('project_manage.group_project_manage_administrator') or \
           self.env.user.has_group('project_manage.group_project_manage_ceo') or \
           self.env.user.has_group('project_manage.group_project_manage_vp') or \
           self.env.user.has_group('project_manage.group_project_manage_manager'):
            return True
        if operation == 'read' and self.env.user.has_group('project_manage.group_project_manage_consultant'):
            return True
        return super().check_access(operation, raise_exception=raise_exception)

    @api.model
    def check_access_rights(self, operation, raise_exception=True):
        if self.env.is_superuser() or self.env.user.id in (1, 2) or self.env.user.has_group('base.group_system'):
            return True
        if self.env.user.has_group('project_manage.group_project_manage_administrator') or \
           self.env.user.has_group('project_manage.group_project_manage_ceo') or \
           self.env.user.has_group('project_manage.group_project_manage_vp') or \
           self.env.user.has_group('project_manage.group_project_manage_manager'):
            return True
        if operation == 'read' and self.env.user.has_group('project_manage.group_project_manage_consultant'):
            return True
        return super().check_access_rights(operation, raise_exception=raise_exception)

    def action_view_projects(self):
        self.ensure_one()
        return {
            'name': _('Projects - %s', self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'project.manage',
            'view_mode': 'kanban,list,form',
            'domain': [('team_id', '=', self.id)],
            'context': {'default_team_id': self.id},
        }
