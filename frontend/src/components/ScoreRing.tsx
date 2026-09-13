function scoreColor(score: number): string {
  if (score >= 70) return "text-green-600";
  if (score >= 40) return "text-amber-500";
  return "text-red-500";
}

export function ScoreRing({ score, label }: { score: number; label: string }) {
  const circumference = 2 * Math.PI * 36;
  const offset = circumference - (score / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative h-24 w-24">
        <svg className="h-24 w-24 -rotate-90" viewBox="0 0 80 80">
          <circle
            cx="40"
            cy="40"
            r="36"
            fill="none"
            stroke="currentColor"
            strokeWidth="6"
            className="text-gray-200"
          />
          <circle
            cx="40"
            cy="40"
            r="36"
            fill="none"
            stroke="currentColor"
            strokeWidth="6"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            className={scoreColor(score)}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className={`text-xl font-semibold ${scoreColor(score)}`}>{score}</span>
        </div>
      </div>
      <span className="text-sm text-gray-500">{label}</span>
    </div>
  );
}
