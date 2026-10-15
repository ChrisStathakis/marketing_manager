import { NavLink, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../lib/auth-store';

const links = [
  ['/', 'Dashboard'],
  ['/campaigns', 'Campaigns'],
  ['/calendar', 'Calendar'],
  ['/results', 'Results'],
  ['/suggestions', 'Suggestions'],
  ['/settings', 'Settings'],
] as const;

export default function Layout({ children }: { children: React.ReactNode }) {
  const { username, logout } = useAuthStore();
  const nav = useNavigate();
  return (
    <div className="shell">
      <aside className="side">
        <div className="brand">Basket Campaigns</div>
        <nav>
          {links.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === '/'}>{label}</NavLink>
          ))}
        </nav>
        <div className="user">
          <span>{username ?? 'user'}</span>
          <button onClick={() => { logout(); nav('/login'); }}>Logout</button>
        </div>
      </aside>
      <main className="main">{children}</main>
    </div>
  );
}
