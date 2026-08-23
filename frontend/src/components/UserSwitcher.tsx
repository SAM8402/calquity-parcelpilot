"use client";

import { useState, useEffect } from "react";

interface UserData {
  id: string;
  name: string;
  role: string;
}

interface UserSwitcherProps {
  selectedUser: string;
  onUserChange: (userId: string) => void;
}

const FALLBACK_USERS: UserData[] = [
  { id: "northstar_user", name: "Alex (Northstar)", role: "customer" },
  { id: "lumenworks_user", name: "Jordan (LumenWorks)", role: "customer" },
  { id: "support_agent", name: "Sam (Support)", role: "support_agent" },
  { id: "ops_manager", name: "Taylor (Ops)", role: "operations" },
];

export default function UserSwitcher({
  selectedUser,
  onUserChange,
}: UserSwitcherProps) {
  const [users, setUsers] = useState<UserData[]>(FALLBACK_USERS);

  useEffect(() => {
    fetch("/api/users")
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) setUsers(data);
      })
      .catch(() => {});
  }, []);

  const currentUser = users.find((u) => u.id === selectedUser);

  return (
    <div className="flex items-center gap-2">
      {currentUser && (
        <span className="hidden border border-paper-line bg-white px-2 py-1 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-muted sm:inline">
          {currentUser.role.replace("_", " ")}
        </span>
      )}
      <label className="sr-only" htmlFor="persona-select">
        Select persona
      </label>
      <select
        id="persona-select"
        value={selectedUser}
        onChange={(e) => onUserChange(e.target.value)}
        className="min-w-[170px] cursor-pointer border border-paper-line bg-white px-3 py-2 text-sm text-ink focus:border-signal focus:outline-none"
      >
        {users.map((user) => (
          <option key={user.id} value={user.id}>
            {user.name}
          </option>
        ))}
      </select>
    </div>
  );
}
