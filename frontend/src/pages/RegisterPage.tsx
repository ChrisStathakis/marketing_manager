import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useAuthStore } from '../lib/auth-store';

const base = () => import.meta.env.VITE_API_URL ?? '/api';

export default function RegisterPage() {
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
          try {
            await axios.post(`${base()}/register/`, { username, password });
            const ok = await login(username, password);
            if (ok) nav('/');
            else nav('/login');
          } catch (ex) {
            if (axios.isAxiosError(ex) && ex.response?.data) {
              const d = ex.response.data as Record<string, string[] | string>;
              const first = Object.entries(d).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(' ') : v}`).join(' ');
              setErr(first || 'Registration failed.');
            } else {
              setErr('Registration failed. Is the API running?');
            }
          }
        }}
      >
        <h1>Create account</h1>
        <label>Username<input value={username} onChange={(e) => setUsername(e.target.value)} required minLength={3} /></label>
        <label>Password (min 4 chars)<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={4} /></label>
        {err && <p role="alert" className="error">{err}</p>}
        <button type="submit">Register</button>
        <p>Have an account? <Link to="/login">Sign in</Link></p>
      </form>
    </div>
  );
}
