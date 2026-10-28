# Crucible Skill Quality Report

- **Report digest:** `sha256:29eedcebcf4bf26cb4f49402e9b43be8477f1b806335b32ee3e0742f1de7498b`
- **Audit digest:** `sha256:60662c6958ed66e9026fe6e465593b514353e02081600ddf22868a851209d47a`
- **Confirmation digest:** `sha256:7e70f73b6bf8639d44b3de149bd3e30bc8a034d1c3dd90e69b8d0c2154716a94`
- **Input:** a skill directory
- **Skills scanned:** 4
- **Recommendations:** MODIFY: 4

## Summary



All four skills examined require modification, with no duplicate groups identified and no rule contradictions found; the text‑only gate accepted two of the four rewrite attempts, indicating partial success in automated fixes, while each skill presents a distinct confirmed finding that drives the recommended changes.  
1. Update the adonisjs skill to resolve the issue recorded in finding-0001.  
2. Update the auth-system-setup skill to resolve the issue recorded in finding-0002.  
3. Update the aws-rds skill to resolve the issue recorded in finding-0003.  
4. Update the batch-processor skill to resolve the issue recorded in finding-0004.  
The audit could not evaluate the checks for BROKEN_REFERENCE, COMPOSITION_CYCLE, CONDITIONAL_CONTRADICTION, NORMATIVE_CONFLICT, ORPHAN_SKILL, and SELF_COMPOSITION because their required inputs were absent from the corpus.

## Duplicate skills to consolidate

Each group is a set of skills joined by confirmed redundancy pairs. The recommendation is to merge each group into one skill; which member survives, and what the merged text says, is not decided here. Add --with-consolidation to have a merge proposed for each group and checked by the deterministic gate.

No confirmed duplicate group in this corpus.

## Contradictions between rules

Not evaluated: the contradiction checks abstained because no two extracted rules share a normalized subject, so this check compared no rule pair. Read this with rules_with_subject: only the RFC-2119 modal extraction route assigns a subject at all, while the negative-starter and imperative routes record an empty one by construction (no object extraction), so a low count usually means a subject was never attempted rather than attempted and unmatched. This is not evidence that the skills agree with each other.

## Rule text repeated across skills

The same rule text appears verbatim in several skills. A repeated block is a candidate for one shared skill or reference document; it is not by itself a defect, and editing one copy leaves the others behind.

No rule text is repeated verbatim across skills.

## Suggested rewrites

4 of 4 skill(s) recommended MODIFY received a suggested rewrite; 2 passed the deterministic gate. The gate re-audits text only, so an accepted rewrite is one the auditor no longer objects to, not evidence of better agent behaviour.

- **adonisjs**
  - Suggested rewrite (llm-nebius): no rewrite was proposed for REQUIREMENT_WITHOUT_CHECK.
- **auth-system-setup**
  - Suggested rewrite (llm-nebius): ACCEPTED by the deterministic gate; resolves REQUIREMENT_WITHOUT_CHECK. The gate re-audits text only: an accepted rewrite is one the auditor no longer objects to, not evidence that an agent following it behaves better.
- **aws-rds**
  - Suggested rewrite (llm-nebius): ACCEPTED by the deterministic gate; resolves REQUIREMENT_WITHOUT_CHECK. The gate re-audits text only: an accepted rewrite is one the auditor no longer objects to, not evidence that an agent following it behaves better.
- **batch-processor**
  - Suggested rewrite (llm-nebius): no rewrite was proposed for REQUIREMENT_WITHOUT_CHECK.

## What was not analyzed

An ABSTAINED check produced no findings because this corpus did not supply the input it consumes; that is not evidence the corpus is free of that defect class.

- **BROKEN_REFERENCE abstained**
  - requires declared_relations, observed 0: the corpus declares no composes_with or delegates_to relation, so this check had no relation to examine
- **COMPOSITION_CYCLE abstained**
  - requires declared_relations, observed 0: the corpus declares no composes_with or delegates_to relation, so this check had no relation to examine
- **CONDITIONAL_CONTRADICTION abstained**
  - requires comparable_rule_pairs_by_subject, observed 0: no two extracted rules share a normalized subject, so this check compared no rule pair. Read this with rules_with_subject: only the RFC-2119 modal extraction route assigns a subject at all, while the negative-starter and imperative routes record an empty one by construction (no object extraction), so a low count usually means a subject was never attempted rather than attempted and unmatched
- **NORMATIVE_CONFLICT abstained**
  - requires comparable_rule_pairs_by_subject, observed 0: no two extracted rules share a normalized subject, so this check compared no rule pair. Read this with rules_with_subject: only the RFC-2119 modal extraction route assigns a subject at all, while the negative-starter and imperative routes record an empty one by construction (no object extraction), so a low count usually means a subject was never attempted rather than attempted and unmatched
- **ORPHAN_SKILL abstained**
  - requires declared_relations, observed 0: the corpus declares no composes_with or delegates_to relation, so this check had no relation to examine
- **SELF_COMPOSITION abstained**
  - requires declared_relations, observed 0: the corpus declares no composes_with or delegates_to relation, so this check had no relation to examine

## Skills

### adonisjs -- MODIFY



The recommendation to MODIFY follows from finding‑0001, which shows that the skill contains a normative rule without any extracted check, violating the invariant that every rule must have an identifiable verification path; therefore the skill must be altered to add the missing checks.  

Next steps:  
1. Locate the unspecified normative rule referenced in finding‑0001 and define a concrete check that verifies its compliance.  
2. Implement the check in the skill’s validation logic (e.g., add a test or runtime assertion).  
3. Update any associated documentation or examples to reflect the new verification path.  
4. Run the skill’s test suite to confirm that the newly added check passes and that no existing functionality is broken.

**Suggested rewrite (llm-nebius): no rewrite was proposed for REQUIREMENT_WITHOUT_CHECK.**

| Finding | Status | Class | Evidence |
|---|---|---|---|
| finding-0001 | CONFIRMED | REQUIREMENT_WITHOUT_CHECK | skill has 1 normative rule(s) but 0 extracted checks |

### auth-system-setup -- MODIFY



The skill contains a normative rule that lacks any associated check, leaving no way to verify that the rule is satisfied (finding-0002). Because verification is missing, the skill must be modified to add a proper verification path or adjust the rule accordingly.

1. Determine what verification is needed for the existing normative rule and specify a concrete check.  
2. Implement the check within the skill’s validation or test suite.  
3. Update any relevant documentation to describe the new verification process.  
4. Re‑run the audit to confirm that finding-0002 is resolved.

**Suggested rewrite (llm-nebius): ACCEPTED by the deterministic gate; resolves REQUIREMENT_WITHOUT_CHECK. The gate re-audits text only: an accepted rewrite is one the auditor no longer objects to, not evidence that an agent following it behaves better.**

<details><summary>Suggested change</summary>

```diff
--- auth-system-setup/SKILL.md (current)
+++ auth-system-setup/SKILL.md (suggested)
@@ -1,128 +1,30 @@
----
-name: auth-system-setup
-description: >-
-  When the user wants to set up authentication and authorization for a web application.
-  Use when the user mentions "auth," "login," "OAuth," "SSO," "single sign-on,"
-  "role-based access," "RBAC," "permissions," "user roles," "access control,"
-  "authentication," or "authorization." Covers OAuth 2.0 provider integration,
-  session management, and role/permission architecture. For JWT-specific tasks,
-  see jwt-handler. For security review, see security-audit.
-license: Apache-2.0
-compatibility: "Any backend framework (Node.js, Python, Go, etc.)"
-metadata:
-  author: terminal-skills
-  version: "1.0.0"
-  category: development
-  tags: ["authentication", "authorization", "oauth", "rbac", "security"]
----
-
-# Auth System Setup
-
-## Overview
-
-Designs and implements complete authentication and authorization systems for web applications. Covers OAuth 2.0 provider integration (Google, GitHub, Microsoft), session and token management, role-based access control (RBAC), and permission architectures. Generates production-ready code, database migrations, and tests.
-
-## Instructions
-
-### 1. Gather Requirements
-
-Before generating any code, determine:
-
-- **Tech stack**: Backend framework, database, frontend framework
-- **Auth method**: OAuth providers, email/password, magic links, or combination
-- **Roles needed**: What roles exist? What can each role do?
-- **Token strategy**: Stateless JWT, server-side sessions, or hybrid
-- **Compliance**: GDPR, SOC 2, HIPAA — affects data storage and logging
-
-### 2. Design the Auth Architecture
-
-Create the auth flow diagram and data model:
-
-- **User table**: id, email, name, avatar, provider, provider_id, created_at
-- **Role table**: id, name, description
-- **Permission table**: id, resource, action (read/write/delete)
-- **Role-Permission mapping**: role_id, permission_id
-- **User-Role mapping**: user_id, role_id
-- **Refresh token table**: id, user_id, token_hash, family_id, expires_at, revoked_at
-
-### 3. Implement OAuth Flow
-
-For each OAuth provider:
-
-1. Create provider configuration (client ID, secret, scopes, callback URL)
-2. Implement the authorization redirect with state parameter and PKCE
-3. Handle the callback: exchange code for tokens, extract user profile
-4. Provision or update the user record
-5. Issue application tokens (access + refresh)
-
-Always use PKCE for public clients. Always validate the state parameter.
-
-### 4. Implement RBAC
-
-Generate the permission-checking middleware:
-
-```
-authorize(resource, action) → middleware function
-  1. Extract user from request (via JWT or session)
-  2. Load user roles and permissions (cache with TTL)
-  3. Check if any role grants the required permission
-  4. Return 403 with clear error if denied
-```
-
-For row-level security, add ownership filters:
-
-```
-filterByOwnership(resource) → middleware function
-  1. If user role has wildcard access, skip filter
-  2. Otherwise, add WHERE clause: resource.owner_id = user.id
-  3. Apply to SELECT, UPDATE, DELETE queries
-```
-
-### 5. Generate Tests
-
-Create tests for:
-
-- OAuth flow: successful login, invalid state, expired code
-- Token lifecycle: issue, refresh, rotate, revoke
-- RBAC: each role accessing allowed and denied resources
-- Edge cases: expired tokens, revoked refresh tokens, role changes mid-session
-
-## Examples
-
-### Example 1: Express + PostgreSQL + Google OAuth
-
-**Prompt**: "Set up Google OAuth with JWT tokens for my Express app. I need admin and user roles."
-
-**Output**:
-- `auth/providers/google.ts` — OAuth 2.0 + PKCE flow
-- `auth/middleware/authenticate.ts` — JWT verification
-- `auth/middleware/authorize.ts` — Role checker
-- `migrations/001_auth_tables.sql` — Users, roles, permissions, refresh_tokens
-- `auth/services/token.service.ts` — JWT issuance with refresh rotation
-- `auth/routes.ts` — /auth/google, /auth/callback, /auth/refresh, /auth/logout
-- `tests/auth.test.ts` — 18 integration tests
-
-### Example 2: Django + GitHub OAuth + Multi-tenant RBAC
-
-**Prompt**: "Add GitHub login to my Django app. Each organization has its own roles: owner, editor, viewer."
-
-**Output**:
-- `accounts/providers/github.py` — OAuth integration via django-allauth
-- `accounts/models.py` — Organization, Membership, Role models
-- `accounts/permissions.py` — Per-organization permission backend
-- `accounts/middleware.py` — Org context middleware (from subdomain or header)
-- `accounts/decorators.py` — @require_org_role('editor') decorator
-- `migrations/0001_multi_tenant_auth.py` — Schema migration
-- `tests/test_permissions.py` — 22 test cases across org boundaries
-
-## Guidelines
-
-- **Never store plain-text passwords** — use bcrypt with cost factor 12+ or argon2id
-- **Always use PKCE** for OAuth flows, even with confidential clients
-- **Rotate refresh tokens** on every use — detect reuse to identify token theft
-- **Set short access token TTL** — 15 minutes is the standard
-- **Cache permissions** — reload on role change, not on every request
-- **Log auth events** — login, logout, failed attempts, role changes (for audit trail)
-- **Rate limit auth endpoints** — prevent brute force on login and token refresh
-- **Use httpOnly, Secure, SameSite=Strict cookies** for refresh tokens in browsers
-- **Never put sensitive data in JWT payload** — it's base64, not encrypted
+---
+name: auth-system-setup
+description: >-
+  When the user wants to set up authentication and authorization for a web application.
+  Use when the user mentions "auth," "login," "OAuth," "SSO," "single sign-on,"
+  "role-based access," "RBAC," "permissions," "user roles," "access control,"
+  "authentication," or "authorization." Covers OAuth 2.0 provider integration,
+  session management, and role/permission architecture. For JWT-specific tasks,
+  see jwt-handler. For security review, see security-audit.
+license: Apache-2.0
+compatibility: "Any backend framework (Node.js, Python, Go, etc.)"
+metadata:
+  author: terminal-skills
+  version: "1.0.0"
+  category: development
+  tags: ["authentication", "authorization", "oauth", "rbac", "security"]
+---
+
+# Auth System Setup
+
+## Overview
+
+Designs and implements complete authentication and authorization systems for web applications. Covers OAuth 2.0 provider integration (Google, GitHub, Microsoft), session and token management, role-based access control (RBAC), and permission architectures. Generates production-ready code, database migrations, and tests.
+
+## Instructions
+
+### 1. Gather Requirements
+
+Before generating any code, determine:\n\n- **Tech stack**: Backend framework, database, frontend framework\n- **Auth method**: OAuth providers, email/password, magic links, or combination\n- **Roles needed**: What roles exist? What can each role do?\n- **Token strategy**: Stateless JWT, server-side sessions, or hybrid\n- **Compliance**: GDPR, SOC 2, HIPAA — affects data storage and logging\n\n### 2. Design the Auth Architecture\n\nCreate the auth flow diagram and data model:\n\n- **User table**: id, email, name, avatar, provider, provider_id, created_at\n- **Role table**: id, name, description\n- **Permission table**: id, resource, action (read/write/delete)\n- **Role-Permission mapping**: role_id, permission_id\n- **User-Role mapping**: user_id, role_id\n- **Refresh token table**: id, user_id, token_hash, family_id, expires_at, revoked_at\n\n### 3. Implement OAuth Flow\n\nFor each OAuth provider:\n\n1. Create provider configuration (client ID, secret, scopes, callback URL)\n2. Implement the authorization redirect with state parameter and PKCE\n3. Handle the callback: exchange code for tokens, extract user profile\n4. Provision or update the user record\n5. Issue application tokens (access + refresh)\n\nAlways use PKCE for public clients. Always validate the state parameter.\n\n### 4. Implement RBAC\n\nGenerate the permission-checking middleware:\n\n```\nauthorize(resource, action) → middleware function\n  1. Extract user from request (via JWT or session)\n  2. Load user roles and permissions (cache with TTL)\n  3. Check if any role grants the required permission\n  4. Return 403 with clear error if denied\n```\n\nFor row-level security, add ownership filters:\n\n```\nfilterByOwnership(resource) → middleware function\n  1. If user role has wildcard access, skip filter\n  2. Otherwise, add WHERE clause: resource.owner_id = user.id\n  3. Apply to SELECT, UPDATE, DELETE queries\n```\n\n### 5. Generate Tests\n\nCreate tests for:\n\n- OAuth flow: successful login, invalid state, expired code\n- Token lifecycle: issue, refresh, rotate, revoke\n- RBAC: each role accessing allowed and denied resources\n- Edge cases: expired tokens, revoked refresh tokens, role changes mid-session\n\n## Examples\n\n### Example 1: Express + PostgreSQL + Google OAuth\n\n**Prompt**: \"Set up Google OAuth with JWT tokens for my Express app. I need admin and user roles.\"\n\n**Output**:\n- `auth/providers/google.ts` — OAuth 2.0 + PKCE flow\n- `auth/middleware/authenticate.ts` — JWT verification\n- `auth/middleware/authorize.ts` — Role checker\n- `migrations/001_auth_tables.sql` — Users, roles, permissions, refresh_tokens\n- `auth/services/token.service.ts` — JWT issuance with refresh rotation\n- `auth/routes.ts` — /auth/google, /auth/callback, /auth/refresh, /auth/logout\n- `tests/auth.test.ts` — 18 integration tests\n\n### Example 2: Django + GitHub OAuth + Multi-tenant RBAC\n\n**Prompt**: \"Add GitHub login to my Django app. Each organization has its own roles: owner, editor, viewer.\"\n\n**Output**:\n- `accounts/providers/github.py` — OAuth integration via django-allauth\n- `accounts/models.py` — Organization, Membership, Role models\n- `accounts/permissions.py` — Per-organization permission backend\n- `accounts/middleware.py` — Org context middleware (from subdomain or header)\n- `accounts/decorators.py` — @require_org_role('editor') decorator\n- `migrations/0001_multi_tenant_auth.py` — Schema migration\n- `tests/test_permissions.py` — 22 test cases across org boundaries\n\n## Guidelines\n\n- **Never store plain-text passwords** — use bcrypt with cost factor 12+ or argon2id\n- **Always use PKCE** for OAuth flows, even with confidential clients\n- **Rotate refresh tokens** on every use — detect reuse to identify token theft\n- **Set short access token TTL** — 15 minutes is the standard\n- **Cache permissions** — reload on role change, not on every request\n- **Log auth events** — login, logout, failed attempts, role changes (for audit trail)\n- **Rate limit auth endpoints** — prevent brute force on login and token refresh\n- **Use httpOnly, Secure, SameSite=Strict cookies** for refresh tokens in browsers\n- **Never put sensitive data in JWT payload** — it's base64, not encrypted\n\n## Checks\n\n- Does the `auth/providers/google.ts` file implement PKCE and validate the state parameter?\n- Does the `auth/middleware/authorize.ts` middleware return a 403 response when a user lacks the required permission?\n- Are the tables defined in `migrations/001_auth_tables.sql` include users, roles, permissions, role_permissions, user_roles, and refresh_tokens?
+---
```

</details>

| Finding | Status | Class | Evidence |
|---|---|---|---|
| finding-0002 | CONFIRMED | REQUIREMENT_WITHOUT_CHECK | skill has 1 normative rule(s) but 0 extracted checks |

### aws-rds -- MODIFY



The skill contains one normative rule but has no extracted checks (finding-0003), meaning there is no verification path for that requirement and the invariant that normative rules should have an identifiable verification path is violated; therefore the skill must be modified to add the missing checks.  

1. Identify the normative rule and define a concrete check that can be extracted and executed.  
2. Implement the check in the skill’s validation logic and link it to the rule.  
3. Run the updated validation to confirm the invariant is satisfied and update any related documentation or tests.

**Suggested rewrite (llm-nebius): ACCEPTED by the deterministic gate; resolves REQUIREMENT_WITHOUT_CHECK. The gate re-audits text only: an accepted rewrite is one the auditor no longer objects to, not evidence that an agent following it behaves better.**

<details><summary>Suggested change</summary>

```diff
--- aws-rds/SKILL.md (current)
+++ aws-rds/SKILL.md (suggested)
@@ -205,2 +205,6 @@
 - Use parameter groups to tune engine settings per workload
 - Place RDS in private subnets; never expose to the public internet
+
+## Checks
+
+- Does the DB instance returned by `aws rds describe-db-instances --db-instance-identifier app-db-prod` show a status of `available`?
```

</details>

| Finding | Status | Class | Evidence |
|---|---|---|---|
| finding-0003 | CONFIRMED | REQUIREMENT_WITHOUT_CHECK | skill has 1 normative rule(s) but 0 extracted checks |

### batch-processor -- MODIFY



The skill contains a normative rule that lacks any corresponding check (finding-0004), violating the invariant that each rule must have an identifiable verification path; therefore the skill must be modified to introduce the missing verification.  

1. Identify the missing verification logic for the sole normative rule.  
2. Implement a concrete check (e.g., a unit test or validation step) that can be extracted and linked to the rule.  
3. Update the skill’s documentation or metadata to reflect the new check and ensure the rule now has a verification path.

**Suggested rewrite (llm-nebius): no rewrite was proposed for REQUIREMENT_WITHOUT_CHECK.**

| Finding | Status | Class | Evidence |
|---|---|---|---|
| finding-0004 | CONFIRMED | REQUIREMENT_WITHOUT_CHECK | skill has 1 normative rule(s) but 0 extracted checks |

## Methodology

The recommendation for every skill (KEEP, NEEDS_CONFIRMATION, MODIFY, or CONSOLIDATE) is computed by a deterministic rule over L2 audit findings and L2.5/L12 confirmation verdicts, before any language model is consulted. The model is given that decision as a fixed fact and asked only to explain it in prose, citing findings by id. Every finding id the model cites is checked after the fact against the sealed findings for that skill; an id that does not exist there is listed as an untraceable claim, not silently presented as evidence. report_digest is the canonical seal of this report: recompute it independently to confirm this rendering was not altered after the fact.
