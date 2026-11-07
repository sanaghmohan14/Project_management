from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProjectManageTask(models.Model):
    _name = 'project.manage.task'
    _description = 'Scope Task (Documentation / Implementation)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'scope_no asc, category asc, item_no asc, id asc'

    name = fields.Char(string='Item / Task Name', required=True, tracking=True)
    item_id = fields.Char(string='Item ID', index=True)
    item_no = fields.Integer(string='Item No')
    category = fields.Selection([
        ('documentation', 'Documentation'),
        ('implementation', 'Implementation'),
    ], string='Category', required=True, index=True, default='documentation', tracking=True)

    item_type = fields.Char(string='Document / Activity Type', tracking=True)
    evidence_proof = fields.Char(string='Evidence / Proof', tracking=True)

    scope_id = fields.Many2one(
        'project.manage.scope', string='Scope', ondelete='cascade',
        required=True, index=True)
    scope_no = fields.Integer(
        related='scope_id.scope_no', store=True, string='Scope No', readonly=True)
    project_id = fields.Many2one(
        'project.manage', string='Project',
        related='scope_id.project_id', store=True, readonly=False, index=True)

    approval_authority = fields.Selection([
        ('TL', 'Team Lead (TL)'),
        ('PM', 'Project Manager (PM)'),
        ('VP', 'Vice President (VP)'),
        ('CEO', 'CEO'),
    ], string='Final Approval Authority', tracking=True)

    accountable_id = fields.Many2one('hr.employee', string='Accountable', tracking=True)
    responsible_id = fields.Many2one('hr.employee', string='Responsible', tracking=True)

    start_date = fields.Date(string='Start Date', tracking=True)
    end_date = fields.Date(string='End Date', tracking=True)

    state = fields.Selection([
        ('todo', 'To Do'),
        ('in_progress', 'In Progress'),
        ('under_review', 'Under Review'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='todo', required=True, tracking=True)

    notes = fields.Text(string='Notes / Instructions')

    def action_start(self):
        for rec in self:
            rec.state = 'in_progress'
            if not rec.start_date:
                rec.start_date = fields.Date.context_today(rec)

    def action_submit_review(self):
        for rec in self:
            rec.state = 'under_review'

    def action_done(self):
        for rec in self:
            rec.state = 'done'
            if not rec.end_date:
                rec.end_date = fields.Date.context_today(rec)

    def action_reset_todo(self):
        for rec in self:
            rec.state = 'todo'

    def action_cancel(self):
        for rec in self:
            rec.state = 'cancelled'
