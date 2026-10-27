// Display labels for M2 roles and permissions. Authorization decisions are
// always made by the backend; the UI only uses these values to decide what to show.

export const ROLE_LABELS = {
  STUDENT: "Student",
  ISSUER: "Issuer",
  ADMIN: "Administrator",
};

export const PERMISSION_LABELS = {
  "profile:read_own": "View your profile",
  "certificate:view_own": "View your certificates",
  "certificate:create": "Create certificates",
  "certificate:issue": "Issue certificates",
  "user:list": "List users",
  "issuer:manage": "Grant and revoke issuer access",
  "admin:manage": "Manage administrators",
};

export function roleLabel(role) {
  return ROLE_LABELS[role] ?? "No role";
}

export function permissionLabel(permission) {
  return PERMISSION_LABELS[permission] ?? permission;
}