package vn.localpilot.app;

/** Deliberately narrow API exposed to the optional Shizuku UserService. */
interface IShizukuDiagnostic {
    void destroy() = 16777114;
    int countUserApps() = 1;
}
