# Kharidino Security Hardening Checklist

This document tracks the security audit and hardening work for Kharidino.

## High priority
- [ ] Remove insecure fallback SECRET_KEY in production.
- [ ] Harden session cookies: Secure, HttpOnly, SameSite.
- [ ] Add CSRF protection to state-changing browser forms/routes.
- [ ] Validate `next` redirects to prevent open redirects.
- [ ] Add security headers (CSP where compatible, X-Content-Type-Options, Referrer-Policy, frame protection, Permissions-Policy).
- [ ] Review every upload endpoint for MIME/content validation and safe storage.
- [ ] Add rate limiting to login/register and sensitive APIs.
- [ ] Audit admin authorization and all POST/DELETE actions.
- [ ] Ensure debug mode is disabled by default in production.
- [ ] Ensure secrets are environment-only and never committed.

## Dependency/runtime
- [ ] Pin or constrain production dependencies.
- [ ] Run automated tests and compile checks.
- [ ] Run route smoke tests.
- [ ] Review mobile API and AI endpoints.

## Verification
- [ ] No hardcoded production secrets.
- [ ] No unsafe redirects.
- [ ] No obvious SQL injection patterns.
- [ ] No obvious command execution from request input.
- [ ] Uploads reject disallowed content.
- [ ] Authentication and authorization tests pass.
