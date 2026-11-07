import base64
from odoo import api, fields, models, _


class ProjectManageScope(models.Model):
    _name = 'project.manage.scope'
    _description = 'Scope & Task Item'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'scope_no asc, category asc, item_no asc, id asc'

    # ---- 12 Exact fields matching the Excel / CSV Import File ----
    item_id = fields.Char(string='Item ID', index=True, tracking=True)
    scope_no = fields.Integer(string='Scope No', index=True, aggregator=None)
    code = fields.Char(string='Code', compute='_compute_code', store=True)
    scope = fields.Char(string='Scope', index=True, tracking=True)
    category = fields.Selection([
        ('Documentation', 'Documentation'),
        ('Implementation', 'Implementation'),
    ], string='Category', index=True, default='Documentation', tracking=True)
    item_no = fields.Integer(string='Item No', aggregator=None)
    name = fields.Char(string='Name', required=True, tracking=True)
    item_type = fields.Char(string='Type', tracking=True)
    evidence_proof = fields.Char(string='Proof', tracking=True)
    accountable = fields.Char(string='Accountable (Text)', tracking=True)
    responsible = fields.Char(string='Responsible (Text)', tracking=True)
    start_date = fields.Date(string='Start Date', tracking=True)
    end_date = fields.Date(string='End Date', tracking=True)

    # ---- Governance, Project & Status ----
    project_id = fields.Many2one(
        'project.manage', string='Project', ondelete='cascade', index=True)
    approval_authority = fields.Selection([
        ('TL', 'Team Lead (TL)'),
        ('PM', 'Project Manager (PM)'),
        ('VP', 'Vice President (VP)'),
        ('CEO', 'CEO'),
    ], string='Approver Role', tracking=True)
    approver_id = fields.Many2one(
        'hr.employee', string='Approver', tracking=True)

    accountable_id = fields.Many2one(
        'hr.employee', string='Accountable', tracking=True)
    responsible_id = fields.Many2one(
        'hr.employee', string='Responsible', tracking=True)

    state = fields.Selection([
        ('todo', 'To Do'),
        ('in_progress', 'In Progress'),
        ('under_review', 'Under Review'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='todo', required=True, tracking=True, group_expand='_group_expand_states')

    # ---- Hierarchical Approval Workflow ----
    approval_state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('pending_tl', 'Waiting Team Lead Approval'),
        ('pending_pm', 'Waiting Project Manager Approval'),
        ('pending_vp', 'Waiting VP Approval'),
        ('pending_ceo', 'Waiting CEO Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected / Re-Work Needed'),
    ], string='Approval Stage', default='draft', tracking=True)

    current_approver_role = fields.Selection([
        ('tl', 'Team Lead (TL)'),
        ('pm', 'Project Manager (PM)'),
        ('vp', 'Vice President (VP)'),
        ('ceo', 'CEO'),
    ], string='Required Approver', compute='_compute_current_approver_role', store=True)

    can_user_approve = fields.Boolean(
        string='Can Current User Approve', compute='_compute_can_user_approve', search='_search_can_user_approve')
    is_my_task = fields.Boolean(
        string='Is Assigned to Current User', compute='_compute_is_my_task', search='_search_is_my_task')

    submitted_by_id = fields.Many2one('res.users', string='Submitted By', tracking=True)
    submitted_date = fields.Datetime(string='Submitted On')
    last_approval_date = fields.Datetime(string='Last Approved On')
    rejection_reason = fields.Text(string='Rejection / Re-Work Notes', tracking=True)

    approval_log_ids = fields.One2many(
        'project.manage.scope.approval.log', 'scope_id', string='Approval History')

    @api.depends('approval_state')
    def _compute_current_approver_role(self):
        role_map = {
            'pending_tl': 'tl',
            'pending_pm': 'pm',
            'pending_vp': 'vp',
            'pending_ceo': 'ceo',
        }
        for rec in self:
            rec.current_approver_role = role_map.get(rec.approval_state, False)

    def _compute_can_user_approve(self):
        user = self.env.user
        is_admin = user.has_group('project_manage.group_project_manage_administrator')
        is_ceo = user.has_group('project_manage.group_project_manage_ceo')
        is_vp = user.has_group('project_manage.group_project_manage_vp')
        is_pm = user.has_group('project_manage.group_project_manage_manager')
        is_tl = user.has_group('project_manage.group_project_manage_team_lead')

        for rec in self:
            st = rec.approval_state
            if not st or st in ('draft', 'in_progress', 'approved'):
                rec.can_user_approve = False
            elif is_admin or is_ceo:
                rec.can_user_approve = True
            elif is_vp and st in ('pending_tl', 'pending_pm', 'pending_vp'):
                rec.can_user_approve = True
            elif is_pm and st in ('pending_tl', 'pending_pm'):
                rec.can_user_approve = True
            elif is_tl and st == 'pending_tl':
                rec.can_user_approve = True
            else:
                rec.can_user_approve = False

    def _compute_is_my_task(self):
        user = self.env.user
        for rec in self:
            rec.is_my_task = (
                (rec.responsible_id.user_id == user) or
                (user in rec.project_id.consultant_ids.mapped('user_id'))
            )

    def _search_can_user_approve(self, operator, value):
        user = self.env.user
        is_admin = user.has_group('project_manage.group_project_manage_administrator')
        is_ceo = user.has_group('project_manage.group_project_manage_ceo')
        is_vp = user.has_group('project_manage.group_project_manage_vp')
        is_pm = user.has_group('project_manage.group_project_manage_manager')
        is_tl = user.has_group('project_manage.group_project_manage_team_lead')

        allowed_states = []
        if is_admin or is_ceo:
            allowed_states = ['pending_tl', 'pending_pm', 'pending_vp', 'pending_ceo']
        elif is_vp:
            allowed_states = ['pending_tl', 'pending_pm', 'pending_vp']
        elif is_pm:
            allowed_states = ['pending_tl', 'pending_pm']
        elif is_tl:
            allowed_states = ['pending_tl']

        positive = (operator == '=' and bool(value)) or (operator in ('!=', '<>') and not bool(value))
        if positive:
            if not allowed_states:
                return [(0, '=', 1)]
            return [('approval_state', 'in', allowed_states)]
        else:
            if not allowed_states:
                return [(1, '=', 1)]
            return ['|', ('approval_state', '=', False), ('approval_state', 'not in', allowed_states)]

    def _search_is_my_task(self, operator, value):
        user = self.env.user
        positive = (operator == '=' and bool(value)) or (operator in ('!=', '<>') and not bool(value))
        domain = [
            '|',
            ('responsible_id.user_id', '=', user.id),
            ('project_id.consultant_ids.user_id', '=', user.id),
        ]
        if positive:
            return domain
        return ['!', *domain]

    color = fields.Integer(string='Color Index')
    notes = fields.Text(string='Notes / Instructions')

    # ---- Uploaded Files & Documents ----
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'project_manage_scope_attachment_rel',
        'scope_id',
        'attachment_id',
        string='Attachments',
    )
    document_ids = fields.One2many(
        'project.manage.scope.document', 'scope_id', string='Documents')
    document_count = fields.Integer(
        string='Document Count', compute='_compute_document_count')

    @api.depends('document_ids', 'attachment_ids')
    def _compute_document_count(self):
        for rec in self:
            rec.document_count = len(rec.document_ids) + len(rec.attachment_ids)

    def _group_expand_states(self, states, domain=None, *args, **kwargs):
        return [key for key, _val in self._fields['state'].selection if key != 'cancelled']

    @api.depends('scope_no')
    def _compute_code(self):
        for rec in self:
            rec.code = f"S{rec.scope_no:02d}" if rec.scope_no is not None else ""

    @api.depends('item_id', 'name')
    def _compute_display_name(self):
        for rec in self:
            if rec.item_id and rec.name:
                rec.display_name = f"[{rec.item_id}] {rec.name}"
            else:
                rec.display_name = rec.name or rec.item_id or _("New Scope Item")

    # Automatically link employee when accountable / responsible text matches
    @api.onchange('responsible_id')
    def _onchange_responsible_id(self):
        if self.responsible_id:
            self.responsible = self.responsible_id.name

    @api.onchange('responsible')
    def _onchange_responsible_text(self):
        if self.responsible and not self.responsible_id:
            emp = self.env['hr.employee'].sudo().search([('name', '=ilike', self.responsible.strip())], limit=1)
            if emp:
                self.responsible_id = emp

    @api.model_create_multi
    @api.model
    def check_access(self, operation, raise_exception=True):
        if self.env.is_superuser() or self.env.user.id in (1, 2) or self.env.user.has_group('base.group_system') or self.env.user.has_group('project_manage.group_project_manage_administrator'):
            return True
        if operation in ('read', 'create', 'write') and self.env.user.has_group('base.group_user'):
            return True
        return super().check_access(operation, raise_exception=raise_exception)

    @api.model
    def check_access_rights(self, operation, raise_exception=True):
        if self.env.is_superuser() or self.env.user.id in (1, 2) or self.env.user.has_group('base.group_system') or self.env.user.has_group('project_manage.group_project_manage_administrator'):
            return True
        if operation in ('read', 'create', 'write') and self.env.user.has_group('base.group_user'):
            return True
        return super().check_access_rights(operation, raise_exception=raise_exception)

    def create(self, vals_list):
        records_vals = [vals_list] if isinstance(vals_list, dict) else (vals_list or [])
        for vals in records_vals:
            if not isinstance(vals, dict):
                continue
            if vals.get('accountable') and not vals.get('accountable_id'):
                emp = self.env['hr.employee'].sudo().search([('name', '=ilike', vals['accountable'])], limit=1)
                if emp:
                    vals['accountable_id'] = emp.id
            if vals.get('responsible') and not vals.get('responsible_id'):
                emp = self.env['hr.employee'].sudo().search([('name', '=ilike', vals['responsible'])], limit=1)
                if emp:
                    vals['responsible_id'] = emp.id
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('accountable') and not vals.get('accountable_id'):
            emp = self.env['hr.employee'].sudo().search([('name', '=ilike', vals['accountable'])], limit=1)
            if emp:
                vals['accountable_id'] = emp.id
        if vals.get('responsible') and not vals.get('responsible_id'):
            emp = self.env['hr.employee'].sudo().search([('name', '=ilike', vals['responsible'])], limit=1)
            if emp:
                vals['responsible_id'] = emp.id
        return super().write(vals)

    # ---- Hierarchical Approval Actions ----
    def action_start(self):
        for rec in self:
            rec.write({
                'state': 'in_progress',
                'approval_state': 'in_progress',
                'start_date': rec.start_date or fields.Date.context_today(rec),
            })

    def action_submit_for_approval(self):
        """Worker completes task, sending it up the hierarchy."""
        user = self.env.user
        for rec in self:
            if rec.approval_state in ('approved', 'pending_tl', 'pending_pm', 'pending_vp', 'pending_ceo'):
                continue

            # Determine starting level based on who completed/is responsible:
            # - If worker is Admin / CEO -> Directly mark Done!
            # - If worker is VP -> goes to CEO
            # - If worker is PM -> goes to VP
            # - If worker is TL -> goes to PM
            # - If worker is Consultant/member -> goes to TL
            if user.has_group('project_manage.group_project_manage_administrator') or user.has_group('project_manage.group_project_manage_ceo'):
                rec.action_approve_level(note=_("Approved directly by Executive."))
                continue
            elif user.has_group('project_manage.group_project_manage_vp'):
                next_stage = 'pending_ceo'
                next_role = 'CEO'
            elif user.has_group('project_manage.group_project_manage_manager') or (rec.project_id.manager_id.user_id == user):
                next_stage = 'pending_vp'
                next_role = 'VP'
            elif user.has_group('project_manage.group_project_manage_team_lead') or (rec.project_id.team_lead_id.user_id == user) or (rec.project_id.team_id.team_lead_id == user):
                next_stage = 'pending_pm'
                next_role = 'Project Manager'
            else:
                next_stage = 'pending_tl'
                next_role = 'Team Lead'

            rec.write({
                'approval_state': next_stage,
                'state': 'under_review',
                'submitted_by_id': user.id,
                'submitted_date': fields.Datetime.now(),
            })

            rec.env['project.manage.scope.approval.log'].create({
                'scope_id': rec.id,
                'user_id': user.id,
                'role_name': user.name,
                'action': 'submit',
                'from_state': 'in_progress',
                'to_state': next_stage,
                'note': _('Task marked complete and submitted for %s approval.', next_role),
            })
            rec.message_post(body=_("Task completion submitted by %s. Waiting for %s approval.", user.name, next_role))

    def action_approve_level(self, note=None):
        """Advances task to the next approval tier in the hierarchy."""
        user = self.env.user
        for rec in self:
            cur = rec.approval_state or 'draft'
            if cur == 'pending_tl':
                next_stage = 'pending_pm'
                role_label = 'Team Lead'
                next_label = 'Project Manager'
            elif cur == 'pending_pm':
                next_stage = 'pending_vp'
                role_label = 'Project Manager'
                next_label = 'Vice President (VP)'
            elif cur == 'pending_vp':
                next_stage = 'pending_ceo'
                role_label = 'Vice President (VP)'
                next_label = 'CEO'
            elif cur in ('pending_ceo', 'draft', 'in_progress', 'rejected', 'under_review'):
                next_stage = 'approved'
                role_label = 'CEO / Executive'
                next_label = 'Done'
            else:
                continue

            vals = {
                'approval_state': next_stage,
                'last_approval_date': fields.Datetime.now(),
            }
            if next_stage == 'approved':
                vals['state'] = 'done'
                if not rec.end_date:
                    vals['end_date'] = fields.Date.context_today(rec)

            rec.write(vals)

            rec.env['project.manage.scope.approval.log'].create({
                'scope_id': rec.id,
                'user_id': user.id,
                'role_name': role_label,
                'action': 'approve',
                'from_state': cur,
                'to_state': next_stage,
                'note': note or (_('Approved by %s. Forwarded to %s.') % (role_label, next_label) if next_stage != 'approved' else _('Final approval granted by %s. Task officially completed.', user.name)),
            })

            if next_stage == 'approved':
                rec.message_post(body=_("Task officially approved and marked Done by %s.", user.name))
            else:
                rec.message_post(body=_("Approved by %s (%s). Forwarded to %s for next review.", user.name, role_label, next_label))

    def action_reject_level(self, reason=None):
        """Approver rejects task and returns it to worker with feedback."""
        user = self.env.user
        for rec in self:
            prev = rec.approval_state
            rec.write({
                'approval_state': 'rejected',
                'state': 'in_progress',
                'rejection_reason': reason or _('Re-work requested by %s.', user.name),
            })
            rec.env['project.manage.scope.approval.log'].create({
                'scope_id': rec.id,
                'user_id': user.id,
                'role_name': user.name,
                'action': 'reject',
                'from_state': prev,
                'to_state': 'rejected',
                'note': reason or _('Rejected by %s. Re-work required.', user.name),
            })
            rec.message_post(body=_("Task rejected by %s. Reason: %s", user.name, reason or _('Re-work required.')))

    def action_open_reject_wizard(self):
        self.ensure_one()
        return {
            'name': _('Reject Task / Request Re-Work'),
            'type': 'ir.actions.act_window',
            'res_model': 'project.manage.scope.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_scope_id': self.id},
        }

    def action_done(self):
        return self.action_approve_level()

    def action_submit_review(self):
        return self.action_submit_for_approval()

    def action_reset_todo(self):
        for rec in self:
            rec.write({
                'state': 'todo',
                'approval_state': 'draft',
                'rejection_reason': False,
            })

    def action_cancel(self):
        for rec in self:
            rec.state = 'cancelled'


class ProjectManageScopeDocument(models.Model):
    _name = 'project.manage.scope.document'
    _description = 'Scope Document & Deliverable'
    _order = 'upload_date desc, id desc'

    @api.model
    def check_access(self, operation, raise_exception=True):
        if self.env.is_superuser() or self.env.user.id in (1, 2) or self.env.user.has_group('base.group_system') or self.env.user.has_group('project_manage.group_project_manage_administrator'):
            return True
        if operation in ('read', 'create', 'write') and self.env.user.has_group('base.group_user'):
            return True
        return super().check_access(operation, raise_exception=raise_exception)

    @api.model
    def check_access_rights(self, operation, raise_exception=True):
        if self.env.is_superuser() or self.env.user.id in (1, 2) or self.env.user.has_group('base.group_system') or self.env.user.has_group('project_manage.group_project_manage_administrator'):
            return True
        if operation in ('read', 'create', 'write') and self.env.user.has_group('base.group_user'):
            return True
        return super().check_access_rights(operation, raise_exception=raise_exception)

    scope_id = fields.Many2one(
        'project.manage.scope', string='Scope Item', ondelete='cascade', required=True)
    name = fields.Char(string='Document Title', required=True)
    file = fields.Binary(string='File', required=True, attachment=True)
    filename = fields.Char(string='File Name')
    doc_type = fields.Selection([
        ('policy', 'Policy'),
        ('sop', 'SOP'),
        ('template', 'Template'),
        ('proof', 'Evidence / Proof'),
        ('deliverable', 'Deliverable'),
        ('other', 'Other'),
    ], string='Category', default='deliverable', required=True)
    file_size = fields.Integer(string='File Size Bytes', compute='_compute_file_size', store=True)
    file_size_display = fields.Char(string='Size', compute='_compute_file_size', store=True)
    uploaded_by = fields.Many2one(
        'res.users', string='Uploaded By', default=lambda self: self.env.user, readonly=True)
    upload_date = fields.Datetime(
        string='Uploaded On', default=fields.Datetime.now, readonly=True)
    notes = fields.Char(string='Notes / Description')

    @api.depends('file')
    def _compute_file_size(self):
        for rec in self:
            if rec.file:
                try:
                    raw_bytes = len(base64.b64decode(rec.file))
                except Exception:
                    raw_bytes = len(rec.file)
                rec.file_size = raw_bytes
                if raw_bytes < 1024:
                    rec.file_size_display = f"{raw_bytes} B"
                elif raw_bytes < 1024 * 1024:
                    rec.file_size_display = f"{raw_bytes / 1024:.1f} KB"
                else:
                    rec.file_size_display = f"{raw_bytes / (1024 * 1024):.1f} MB"
            else:
                rec.file_size = 0
                rec.file_size_display = "0 B"


class ProjectManageScopeApprovalLog(models.Model):
    _name = 'project.manage.scope.approval.log'
    _description = 'Task Approval Audit Log'
    _order = 'date desc, id desc'

    scope_id = fields.Many2one('project.manage.scope', string='Task Item', ondelete='cascade', required=True)
    user_id = fields.Many2one('res.users', string='Action By', default=lambda self: self.env.user)
    role_name = fields.Char(string='Role / Approver')
    action = fields.Selection([
        ('submit', 'Submitted'),
        ('approve', 'Approved'),
        ('reject', 'Rejected'),
        ('reset', 'Reset'),
    ], string='Action', required=True)
    from_state = fields.Char(string='From Stage')
    to_state = fields.Char(string='To Stage')
    note = fields.Text(string='Comments / Feedback')
    date = fields.Datetime(string='Timestamp', default=fields.Datetime.now, readonly=True)


class ProjectManageScopeRejectWizard(models.TransientModel):
    _name = 'project.manage.scope.reject.wizard'
    _description = 'Reject Task and Request Re-work'

    scope_id = fields.Many2one('project.manage.scope', string='Task Item', required=True)
    reason = fields.Text(string='Rejection Reason / Required Changes', required=True)

    def action_confirm_reject(self):
        self.ensure_one()
        return self.scope_id.action_reject_level(reason=self.reason)
