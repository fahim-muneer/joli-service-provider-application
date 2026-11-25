// The ONE place that knows about the three kinds of user.
// Every other file asks this table instead of hard-coding "/login" or "/provider".
//
//   portal  = which door the person walks through (sent to the backend on login).
//             It is the same word as the user's `role`.
export const ROLES = {
  customer: {
    label: "Customer",
    loginPath: "/login",
    registerPath: "/register",
    verifyPath: "/verify-phone",
    home: "/", // the public site
  },
  provider: {
    label: "Service provider",
    loginPath: "/provider/login",
    registerPath: "/provider/register",
    verifyPath: "/provider/verify-phone",
    home: "/provider", // provider dashboard
  },
  admin: {
    label: "Admin",
    loginPath: "/admin/login",
    registerPath: null, // admins are never self-registered: they are created by staff
    home: "/admin", // admin dashboard
  },
};

/** Where a signed-in user of this role lands. */
export const homeFor = (role) => ROLES[role]?.home ?? "/";

/** Which login page belongs to this role. */
export const loginFor = (role) => ROLES[role]?.loginPath ?? ROLES.customer.loginPath;
