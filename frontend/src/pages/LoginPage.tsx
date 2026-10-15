import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../lib/auth-store';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [err, setErr] = useState('');
  const login = useAuthStore((s) => s.login);
  const nav = useNavigate();
  return (
    <div className="center">
      <form
        className="card"
        onSubmit={async (e) => {
          e.preventDefault();
          setErr('');
          const ok = await login(username, password);
          if (ok) nav('/');
          else setErr('Invalid credentials. Create a Django user first (createsuperuser).');
        }}
      >
        <h1>Sign in</h1>
        <label>Username<input value={username} onChange={(e) => setUsername(e.target.value)} required /></label>
        <label>Password<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required /></label>
        {err && <p role="alert" className="error">{err}</p>}
        <button type="submit">Login</button>
        <p>No account? <Link to="/register">Create one</Link></p>
      </form>
    </div>
  );
}
