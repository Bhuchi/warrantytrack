"use client";

import { usePathname } from "next/navigation";
import { useState } from "react";
import type { ReactNode } from "react";

import AppBar from "@/components/AppBar";
import NavPanel from "@/components/NavPanel";
import type { NavUser, NavWorkspace } from "@/components/NavPanel";

/**
 * Chrome for every signed-in screen: the navigation panel plus the mobile top
 * bar. It owns whether the drawer is open, because both the hamburger that
 * opens it and the panel that closes it need to agree on one value.
 */

interface AppShellProps {
  children: ReactNode;
  workspace: NavWorkspace;
  user: NavUser | null;
  unreadCount: number;
}

export default function AppShell({
  children,
  workspace,
  user,
  unreadCount,
}: AppShellProps) {
  const [navOpen, setNavOpen] = useState(false);
  const pathname = usePathname();
  const hideAppBar = pathname === "/notifications" || pathname === "/settings";
  const closeNav = () => setNavOpen(false);

  return (
    <div className="flex min-h-screen flex-1 bg-canvas">
      {/* Backdrop. Only on mobile — on desktop the panel is pinned open, so
          there is nothing to dismiss. */}
      {navOpen && (
        <button
          type="button"
          aria-hidden="true"
          tabIndex={-1}
          onClick={closeNav}
          className="fixed inset-0 z-30 bg-black/40 md:hidden"
        />
      )}

      <NavPanel
        open={navOpen}
        onClose={closeNav}
        workspace={workspace}
        user={user}
        unreadCount={unreadCount}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        {!hideAppBar && (
          <AppBar
            onMenuClick={() => setNavOpen(true)}
            initials={user?.initials ?? workspace.initials}
            unreadCount={unreadCount}
          />
        )}
        {children}
      </div>
    </div>
  );
}
