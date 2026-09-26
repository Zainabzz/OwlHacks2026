function App() {
  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center">
      <div className="rounded-2xl bg-slate-800 p-8 text-center shadow-xl">
        <h1 className="text-3xl font-bold text-blue-400">
          OwlHacks 2026
        </h1>

        <p className="mt-3 text-slate-300">
          Weather-aware routing app
        </p>

        <button className="mt-6 rounded-lg bg-blue-600 px-6 py-3 font-semibold text-white hover:bg-blue-500">
          Find a Route
        </button>
      </div>
    </div>
  )
}

export default App