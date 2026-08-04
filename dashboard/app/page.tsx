"use client";

import { useEffect, useState } from "react";

const apiUrl = process.env.NEXT_PUBLIC_API_URL || "/api/status";

export default function HomePage() {
  const [status, setStatus] = useState<string | null>(null);
  const [message, setMessage] = useState<string>("Checking dashboard API...");

  useEffect(() => {
    async function fetchStatus() {
      try {
        const response = await fetch(apiUrl, { cache: "no-store" });
        const data = await response.json();
        setStatus(data.status || "unknown");
        setMessage(`Dashboard API reachable at ${apiUrl}`);
      } catch (error) {
        setStatus("offline");
        setMessage(`Unable to reach API at ${apiUrl}. Please configure NEXT_PUBLIC_API_URL or use the built-in /api/status route.`);
      }
    }
    fetchStatus();
  }, []);

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 px-6 py-12">
      <div className="mx-auto max-w-4xl rounded-3xl border border-slate-800 bg-slate-900/95 p-10 shadow-2xl shadow-black/40">
        <h1 className="text-4xl font-extrabold tracking-tight text-white">Bezms Bot Dashboard</h1>
        <p className="mt-4 text-slate-400">One place for safe, fast, and stable server management.</p>

        <section className="mt-10 grid gap-6 sm:grid-cols-2">
          <div className="rounded-3xl border border-slate-800 bg-slate-950 p-6">
            <h2 className="text-xl font-semibold text-white">Bot Information</h2>
            <p className="mt-3 text-slate-400">Bot Name: Bezms Bot</p>
            <p className="text-slate-400">Prefix: {process.env.NEXT_PUBLIC_BOT_PREFIX || ">"}</p>
            <p className="text-slate-400">Invite: <a className="text-red-400 hover:text-red-300" href="https://discord.gg/9nKHrnWZqV">discord.gg/9nKHrnWZqV</a></p>
          </div>

          <div className="rounded-3xl border border-slate-800 bg-slate-950 p-6">
            <h2 className="text-xl font-semibold text-white">Dashboard Status</h2>
            <p className="mt-3 text-slate-400">{message}</p>
            <p className="mt-2 text-slate-400">API Status: <span className="font-semibold text-white">{status || "loading"}</span></p>
            <p className="mt-2 text-slate-400">API Endpoint: <span className="font-mono text-sm text-slate-200">{apiUrl}</span></p>
          </div>
        </section>

        <div className="mt-10 rounded-3xl border border-slate-800 bg-slate-950 p-6">
          <h2 className="text-xl font-semibold text-white">Dashboard Notes</h2>
          <ul className="mt-4 list-disc space-y-2 pl-5 text-slate-400">
            <li>Use <span className="text-white">NEXT_PUBLIC_API_URL</span> to point to the Railway bot API when deployed.</li>
            <li>Built for Vercel with a production-ready status API endpoint at <span className="text-white">/api/status</span>.</li>
            <li>This dashboard is intentionally light and fast so the build completes reliably.</li>
          </ul>
        </div>
      </div>
    </main>
  );
}
