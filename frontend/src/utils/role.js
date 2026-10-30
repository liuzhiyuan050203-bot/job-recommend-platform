const ROLE_HOME = {
  student: '/student',
  company: '/company',
  admin: '/admin'
}

export function roleHome(roleName) {
  return ROLE_HOME[roleName] || '/'
}

export function isSafeRedirect(redirect, roleName) {
  if (typeof redirect !== 'string' || !redirect.startsWith('/') || redirect.startsWith('//')) {
    return false
  }
  const prefix = ROLE_HOME[roleName]
  if (!prefix) {
    return false
  }
  return redirect === prefix || redirect.startsWith(`${prefix}/`)
}
