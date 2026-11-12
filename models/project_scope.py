import base64
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.fields import Domain
from .scope_master_data import get_default_approval_authority



class ProjectManageScope(models.Model):
    _name = 'project.manage.scope'
    _description = 'Scope & Task Item'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, scope_no asc, category asc, item_no asc, id asc'

    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Low'),
        ('2', 'High'),
        ('3', 'Very High'),
    ], string='Priority', default='0', index=True, tracking=True)

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
    evidence_proof = fields.Char(string='Proof / Evidence', tracking=True)
    approval_authority = fields.Selection([
        ('TL', 'Team Lead (TL)'),
        ('PM', 'Project Manager (PM)'),
        ('VP', 'Vice President (VP)'),
        ('CEO', 'CEO'),
    ], string='Final Approval Authority', index=True, default='TL', tracking=True)

    @api.onchange('item_id', 'scope_no', 'category', 'item_no', 'name')
    def _onchange_auto_fill_approval_authority(self):
        if not self.approval_authority:
            auth = get_default_approval_authority(
                item_id=self.item_id,
                scope_no=self.scope_no,
                category=self.category,
                item_no=self.item_no,
                name=self.name,
            )
            if auth:
                self.approval_authority = auth
    accountable_id = fields.Many2one('hr.employee', string='Accountable', index=True, tracking=True)
    responsible_id = fields.Many2one('hr.employee', string='Responsible', tracking=True)
    start_date = fields.Date(string='Start Date', tracking=True, default=fields.Date.context_today)
    end_date = fields.Date(string='End Date', tracking=True, default=fields.Date.context_today)

    @api.onchange('start_date')
    def _onchange_start_date(self):
        if self.start_date and (not self.end_date or self.end_date < self.start_date):
            self.end_date = self.start_date

    @api.onchange('end_date')
    def _onchange_end_date(self):
        if self.end_date and (not self.start_date or self.start_date > self.end_date):
            self.start_date = self.end_date

    # Computed compatibility strings for legacy Python references
    accountable = fields.Char(string='Accountable', compute='_compute_accountable_str', store=False)
    responsible = fields.Char(string='Responsible', compute='_compute_responsible_str', store=False)

    @api.depends('accountable_id')
    def _compute_accountable_str(self):
        for rec in self:
            rec.accountable = rec.accountable_id.name if rec.accountable_id else ''

    @api.depends('responsible_id')
    def _compute_responsible_str(self):
        for rec in self:
            rec.responsible = rec.responsible_id.name if rec.responsible_id else ''

    # ---- Governance, Project & Status ----
    project_id = fields.Many2one(
        'project.manage', string='Project', ondelete='cascade', index=True)

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
    can_edit_scope_fields = fields.Boolean(
        string='Can Edit Scope Fields', compute='_compute_can_edit_scope_fields')
    can_current_user_complete = fields.Boolean(
        string='Can Complete Task', compute='_compute_can_current_user_complete')

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
        emp_domain = [('user_id', '=', user.id)]
        if user.email:
            emp_domain = ['|', ('user_id', '=', user.id), ('work_email', '=ilike', user.email.strip())]
        current_emps = self.env['hr.employee'].sudo().search(emp_domain)
        emp_ids = set(current_emps.ids)

        is_admin = bool(
            self.env.is_superuser() or
            user.id in (1, 2) or
            user.has_group('base.group_system') or
            user.has_group('base.group_erp_manager') or
            user.has_group('project_manage.group_project_manage_administrator')
        )
        is_ceo = bool(is_admin or user.has_group('project_manage.group_project_manage_ceo'))
        is_vp = bool(is_ceo or user.has_group('project_manage.group_project_manage_vp'))
        is_pm = bool(is_vp or user.has_group('project_manage.group_project_manage_manager'))
        is_tl = bool(is_pm or user.has_group('project_manage.group_project_manage_team_lead'))

        for rec in self:
            st = rec.approval_state
            if not st or st in ('draft', 'in_progress', 'todo', 'approved', 'rejected'):
                rec.can_user_approve = False
                continue

            if is_admin or is_ceo:
                rec.can_user_approve = True
                continue

            if is_vp:
                rec.can_user_approve = True
                continue

            proj = rec.project_id
            is_proj_pm = bool(
                proj and (
                    proj.manager_id.user_id == user or
                    proj.manager_id.id in emp_ids
                )
            )
            is_proj_tl = bool(
                proj and (
                    proj.team_lead_id.user_id == user or
                    proj.team_lead_id.id in emp_ids or
                    proj.team_id.team_lead_id == user
                )
            )
            has_no_tl = bool(proj and not proj.team_lead_id and not proj.team_id.team_lead_id)
            has_no_pm = bool(proj and not proj.manager_id)

            if st == 'pending_ceo':
                rec.can_user_approve = is_ceo
            elif st == 'pending_vp':
                rec.can_user_approve = is_vp
            elif st == 'pending_pm':
                # Came specifically for Project Manager of this project
                rec.can_user_approve = bool(is_proj_pm or (is_pm and has_no_pm))
            elif st == 'pending_tl':
                # Came specifically for Team Lead of this project
                rec.can_user_approve = bool(
                    is_proj_tl or
                    (is_proj_pm and has_no_tl) or
                    (is_tl and has_no_tl and has_no_pm)
                )
            else:
                rec.can_user_approve = False

    def _compute_is_my_task(self):
        user = self.env.user
        for rec in self:
            rec.is_my_task = (
                (rec.responsible_id.user_id == user) or
                (user in rec.project_id.consultant_ids.mapped('user_id'))
            )

    def _compute_can_edit_scope_fields(self):
        user = self.env.user
        can_edit = bool(
            self.env.is_superuser() or
            user.id in (1, 2) or
            user.has_group('base.group_system') or
            user.has_group('project_manage.group_project_manage_administrator') or
            user.has_group('project_manage.group_project_manage_ceo') or
            user.has_group('project_manage.group_project_manage_vp') or
            user.has_group('project_manage.group_project_manage_manager') or
            user.has_group('project_manage.group_project_manage_team_lead')
        )
        for rec in self:
            rec.can_edit_scope_fields = can_edit

    def _compute_can_current_user_complete(self):
        user = self.env.user
        current_emp = self.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
        is_admin = bool(
            self.env.is_superuser() or
            user.id in (1, 2) or
            user.has_group('base.group_system') or
            user.has_group('project_manage.group_project_manage_administrator')
        )
        for rec in self:
            if rec.state == 'done' or rec.approval_state in ('approved', 'pending_tl', 'pending_pm', 'pending_vp', 'pending_ceo'):
                rec.can_current_user_complete = False
                continue

            if not rec.responsible_id:
                rec.can_current_user_complete = False
                continue

            is_assigned = bool(
                (rec.responsible_id.user_id == user) or
                (current_emp and rec.responsible_id == current_emp)
            )
            rec.can_current_user_complete = bool(is_assigned or is_admin)

    def _search_can_user_approve(self, operator, value):
        user = self.env.user
        positive = (operator == '=' and bool(value)) or (operator in ('!=', '<>') and not bool(value))

        emp_domain = [('user_id', '=', user.id)]
        if user.email:
            emp_domain = ['|', ('user_id', '=', user.id), ('work_email', '=ilike', user.email.strip())]
        current_emps = self.env['hr.employee'].sudo().search(emp_domain)
        emp_ids = current_emps.ids

        is_admin = bool(
            self.env.is_superuser() or
            user.id in (1, 2) or
            user.has_group('base.group_system') or
            user.has_group('base.group_erp_manager') or
            user.has_group('project_manage.group_project_manage_administrator')
        )
        is_ceo = bool(is_admin or user.has_group('project_manage.group_project_manage_ceo'))
        is_vp = bool(is_ceo or user.has_group('project_manage.group_project_manage_vp'))
        is_pm = bool(is_vp or user.has_group('project_manage.group_project_manage_manager'))
        is_tl = bool(is_pm or user.has_group('project_manage.group_project_manage_team_lead'))

        if is_admin or is_ceo:
            admin_domain = [('approval_state', 'in', ('pending_tl', 'pending_pm', 'pending_vp', 'pending_ceo'))]
            return admin_domain if positive else list(Domain(['!'] + admin_domain))

        domains_list = []

        # 1. VP stage
        if is_vp:
            domains_list.append([('approval_state', '=', 'pending_vp')])

        # 2. PM stage ('pending_pm')
        pm_match = [('project_id.manager_id.user_id', '=', user.id)]
        if emp_ids:
            pm_match.append(('project_id.manager_id', 'in', emp_ids))
        if is_pm:
            pm_match.append(('project_id.manager_id', '=', False))

        pm_assigned_domain = list(Domain.OR([[cond] for cond in pm_match]))
        pm_full_domain = list(Domain.AND([[('approval_state', '=', 'pending_pm')], pm_assigned_domain]))
        if is_vp:
            pm_full_domain = [('approval_state', '=', 'pending_pm')]
        domains_list.append(pm_full_domain)

        # 3. TL stage ('pending_tl')
        tl_match = [
            ('project_id.team_lead_id.user_id', '=', user.id),
            ('project_id.team_id.team_lead_id', '=', user.id),
        ]
        if emp_ids:
            tl_match.append(('project_id.team_lead_id', 'in', emp_ids))

        no_tl_domain = list(Domain.AND([
            [('project_id.team_lead_id', '=', False)],
            [('project_id.team_id.team_lead_id', '=', False)],
        ]))
        pm_fallback_domain = list(Domain.AND([pm_assigned_domain, no_tl_domain]))

        tl_options = [[m] for m in tl_match]
        tl_options.append(pm_fallback_domain)
        if is_tl:
            tl_options.append(no_tl_domain)

        tl_assigned_domain = list(Domain.OR(tl_options))
        tl_full_domain = list(Domain.AND([[('approval_state', '=', 'pending_tl')], tl_assigned_domain]))
        if is_vp:
            tl_full_domain = [('approval_state', '=', 'pending_tl')]
        domains_list.append(tl_full_domain)

        full_domain = list(Domain.OR(domains_list)) if domains_list else [(0, '=', 1)]

        if positive:
            return full_domain
        return list(Domain(['!'] + full_domain))

    def _search_is_my_task(self, operator, value):
        user = self.env.user
        positive = (operator == '=' and bool(value)) or (operator in ('!=', '<>') and not bool(value))
        emp_domain = [('user_id', '=', user.id)]
        if user.email:
            emp_domain = ['|', ('user_id', '=', user.id), ('work_email', '=ilike', user.email.strip())]
        current_emps = self.env['hr.employee'].sudo().search(emp_domain)
        emp_ids = current_emps.ids
        match_terms = [
            ('responsible_id.user_id', '=', user.id),
            ('project_id.consultant_ids.user_id', '=', user.id),
        ]
        if emp_ids:
            match_terms.append(('responsible_id', 'in', emp_ids))
            match_terms.append(('project_id.consultant_ids', 'in', emp_ids))
        domain = list(Domain.OR([[t] for t in match_terms]))
        if positive:
            return domain
        return list(Domain(['!'] + domain))

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

    # Automatically link employee when responsible text matches
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

    @api.model_create_multi
    def create(self, vals_list):
        records_vals = [vals_list] if isinstance(vals_list, dict) else (vals_list or [])
        for vals in records_vals:
            if not isinstance(vals, dict):
                continue
            # Remove legacy text keys if present; user assigns accountable_id and responsible_id manually
            vals.pop('responsible', None)
            vals.pop('accountable', None)

            if not vals.get('approval_authority'):
                auth = get_default_approval_authority(
                    item_id=vals.get('item_id'),
                    scope_no=vals.get('scope_no'),
                    category=vals.get('category'),
                    item_no=vals.get('item_no'),
                    name=vals.get('name'),
                )
                if auth:
                    vals['approval_authority'] = auth

            # Ensure both start_date and end_date for calendar view
            if vals.get('start_date') and not vals.get('end_date'):
                vals['end_date'] = vals['start_date']
            elif vals.get('end_date') and not vals.get('start_date'):
                vals['start_date'] = vals['end_date']

        return super().create(vals_list)

    def write(self, vals):
        # Remove legacy text keys if present
        vals.pop('responsible', None)
        vals.pop('accountable', None)

        user = self.env.user
        is_privileged = bool(
            self.env.is_superuser() or
            user.id in (1, 2) or
            user.has_group('base.group_system') or
            user.has_group('project_manage.group_project_manage_administrator') or
            user.has_group('project_manage.group_project_manage_ceo') or
            user.has_group('project_manage.group_project_manage_vp') or
            user.has_group('project_manage.group_project_manage_manager') or
            user.has_group('project_manage.group_project_manage_team_lead')
        )
        if not is_privileged:
            # Consultants cannot edit scope, governance, approval authority or schedule fields
            restricted_fields = {
                'name', 'item_id', 'scope_no', 'scope', 'category', 'item_no',
                'item_type', 'evidence_proof', 'approval_authority',
                'accountable_id', 'responsible_id', 'start_date', 'end_date', 'project_id'
            }
            for rf in restricted_fields:
                vals.pop(rf, None)

        if vals.get('state') == 'under_review' and not vals.get('approval_state'):
            vals['approval_state'] = 'pending_tl'
            if not vals.get('submitted_by_id'):
                vals['submitted_by_id'] = self.env.user.id
            if not vals.get('submitted_date'):
                vals['submitted_date'] = fields.Datetime.now()
        elif vals.get('state') == 'done' and not vals.get('approval_state'):
            vals['approval_state'] = 'approved'
        elif vals.get('state') == 'todo' and not vals.get('approval_state'):
            vals['approval_state'] = 'draft'

        if vals.get('start_date') and not vals.get('end_date') and not any(r.end_date for r in self):
            vals['end_date'] = vals['start_date']
        elif vals.get('end_date') and not vals.get('start_date') and not any(r.start_date for r in self):
            vals['start_date'] = vals['end_date']

        return super().write(vals)

    # ---- Hierarchical Approval Actions ----
    def action_start(self):
        user = self.env.user
        current_emp = self.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
        is_admin = bool(
            self.env.is_superuser() or
            user.id in (1, 2) or
            user.has_group('base.group_system') or
            user.has_group('project_manage.group_project_manage_administrator')
        )
        for rec in self:
            if not is_admin:
                if not rec.responsible_id:
                    raise UserError(_("This task cannot be started because no responsible employee is assigned."))
                is_assigned = (
                    (rec.responsible_id.user_id == user) or
                    (current_emp and rec.responsible_id == current_emp)
                )
                if not is_assigned:
                    raise UserError(_("Only the task assigned employee (%s) has the right to start this task.", rec.responsible_id.name))

            rec.write({
                'state': 'in_progress',
                'approval_state': 'in_progress',
                'start_date': rec.start_date or fields.Date.context_today(rec),
            })
            rec.env['project.manage.scope.approval.log'].sudo().create({
                'scope_id': rec.id,
                'user_id': self.env.user.id,
                'role_name': self.env.user.name,
                'action': 'start',
                'from_state': 'todo',
                'to_state': 'in_progress',
                'note': _('Task started by %s.', self.env.user.name),
            })

    def action_submit_for_approval(self):
        """Worker completes task, submitting it into the tier-by-tier approval workflow.
        The hierarchy begins with Team Lead review (pending_tl).
        """
        user = self.env.user
        current_emp = self.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
        is_admin = bool(
            self.env.is_superuser() or
            user.id in (1, 2) or
            user.has_group('base.group_system') or
            user.has_group('project_manage.group_project_manage_administrator')
        )

        for rec in self:
            if not is_admin:
                if not rec.responsible_id:
                    raise UserError(_("This task cannot be completed because no responsible employee is assigned."))
                is_assigned = (
                    (rec.responsible_id.user_id == user) or
                    (current_emp and rec.responsible_id == current_emp)
                )
                if not is_assigned:
                    raise UserError(_("Only the task assigned employee (%s) has the right to complete this task.", rec.responsible_id.name))

            if rec.approval_state in ('approved', 'pending_tl', 'pending_pm', 'pending_vp', 'pending_ceo'):
                continue

            final_auth = (rec.approval_authority or 'TL').upper()

            # Task always enters hierarchy at Tier 1: Team Lead review
            next_stage = 'pending_tl'
            next_role = 'Team Lead'

            rec.write({
                'approval_state': next_stage,
                'state': 'under_review',
                'submitted_by_id': user.id,
                'submitted_date': fields.Datetime.now(),
            })

            rec.env['project.manage.scope.approval.log'].sudo().create({
                'scope_id': rec.id,
                'user_id': user.id,
                'role_name': user.name,
                'action': 'submit',
                'from_state': rec.state or 'in_progress',
                'to_state': next_stage,
                'note': _('Task completed by %s and submitted for %s approval (Final Authority: %s).', user.name, next_role, final_auth),
            })
            rec.message_post(body=_("Task completion submitted by %s. Waiting for %s approval (Final Authority: %s).", user.name, next_role, final_auth))

    def action_approve_level(self, note=None):
        """Advances task strictly through the approval hierarchy based on current stage and designated final approval authority:
        - Hierarchy order: Consultant (completes) -> Team Lead (pending_tl) -> Project Manager (pending_pm) -> Vice President (pending_vp) -> CEO (pending_ceo)
        - If final authority is TL:
            pending_tl -> Approved (Done) immediately (does NOT go to PM).
        - If final authority is PM:
            pending_tl -> pending_pm -> Approved (Done) immediately (does NOT go to VP).
        - If final authority is VP:
            pending_tl -> pending_pm -> pending_vp -> Approved (Done) immediately (does NOT go to CEO).
        - If final authority is CEO:
            pending_tl -> pending_pm -> pending_vp -> pending_ceo -> Approved (Done).
        """
        user = self.env.user
        for rec in self:
            if not rec.can_user_approve:
                raise UserError(_("You are not authorized to approve this task (%s) at stage %s.") % (rec.name, rec.approval_state))
            cur = rec.approval_state or 'draft'
            final_auth = (rec.approval_authority or 'TL').upper()

            if cur == 'pending_tl':
                role_label = 'Team Lead'
                if final_auth == 'TL':
                    next_stage = 'approved'
                    next_label = 'Done'
                else:
                    next_stage = 'pending_pm'
                    next_label = 'Project Manager'

            elif cur == 'pending_pm':
                role_label = 'Project Manager'
                if final_auth == 'PM':
                    next_stage = 'approved'
                    next_label = 'Done'
                else:
                    next_stage = 'pending_vp'
                    next_label = 'Vice President (VP)'

            elif cur == 'pending_vp':
                role_label = 'Vice President (VP)'
                if final_auth == 'VP':
                    next_stage = 'approved'
                    next_label = 'Done'
                else:
                    next_stage = 'pending_ceo'
                    next_label = 'CEO'

            elif cur == 'pending_ceo':
                role_label = 'CEO'
                next_stage = 'approved'
                next_label = 'Done'

            elif cur in ('draft', 'in_progress', 'todo', 'rejected', 'under_review'):
                # Fallback if approve is triggered directly before submit
                role_label = 'Team Lead'
                if final_auth == 'TL':
                    next_stage = 'approved'
                    next_label = 'Done'
                else:
                    next_stage = 'pending_pm'
                    next_label = 'Project Manager'

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

            rec.env['project.manage.scope.approval.log'].sudo().create({
                'scope_id': rec.id,
                'user_id': user.id,
                'role_name': role_label,
                'action': 'approve',
                'from_state': cur,
                'to_state': next_stage,
                'note': note or (
                    _('Approved by %s (%s). Forwarded to %s for next review.') % (user.name, role_label, next_label)
                    if next_stage != 'approved'
                    else _('Final approval granted by %s (%s). Task officially completed.', user.name, role_label)
                ),
            })

            if next_stage == 'approved':
                rec.message_post(body=_("Task officially approved and marked Done by %s (Final Authority: %s).", user.name, final_auth))
            else:
                rec.message_post(body=_("Approved by %s (%s). Forwarded to %s for review (Final Authority: %s).", user.name, role_label, next_label, final_auth))

    def action_populate_approval_authority(self):
        """Mass action to populate/pre-fill final approval authority from master data."""
        updated = 0
        for rec in self:
            auth = get_default_approval_authority(
                item_id=rec.item_id,
                scope_no=rec.scope_no,
                category=rec.category,
                item_no=rec.item_no,
                name=rec.name,
            )
            if auth and rec.approval_authority != auth:
                rec.approval_authority = auth
                updated += 1
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Approver Roles Updated'),
                'message': _('Pre-filled approval authority on %s scope item(s).', updated),
                'type': 'success',
                'sticky': False,
            }
        }

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
            rec.env['project.manage.scope.approval.log'].sudo().create({
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
        ('start', 'Started'),
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
