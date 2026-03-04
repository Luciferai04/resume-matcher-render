'use client';

import React from 'react';
import { ATSScore } from '@/lib/api/resume';

interface ATSScoreProps {
    score: ATSScore;
}

const ATSScoreComponent: React.FC<ATSScoreProps> = ({ score }) => {
    const getColor = (value: number) => {
        if (value >= 80) return 'text-green-600';
        if (value >= 60) return 'text-yellow-600';
        return 'text-red-600';
    };

    const getBgColor = (value: number) => {
        if (value >= 80) return 'bg-green-100';
        if (value >= 60) return 'bg-yellow-100';
        return 'bg-red-100';
    };

    return (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm">
            <div className="bg-slate-50 px-6 py-4 border-b border-slate-200 flex justify-between items-center">
                <h3 className="text-lg font-semibold text-slate-800">ATS Match Score</h3>
                <div className={`px-4 py-1 rounded-full font-bold text-xl ${getBgColor(score.totalScore)} ${getColor(score.totalScore)}`}>
                    {score.totalScore}%
                </div>
            </div>

            <div className="p-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
                    <div>
                        <div className="flex justify-between mb-2">
                            <span className="text-sm font-medium text-slate-600">Keyword Match</span>
                            <span className="text-sm font-semibold">{score.breakdown.keywordMatch}/40</span>
                        </div>
                        <div className="w-full bg-slate-100 rounded-full h-2">
                            <div
                                className="bg-blue-500 h-2 rounded-full transition-all duration-500"
                                style={{ width: `${(score.breakdown.keywordMatch / 40) * 100}%` }}
                            />
                        </div>
                    </div>

                    <div>
                        <div className="flex justify-between mb-2">
                            <span className="text-sm font-medium text-slate-600">Structural Completeness</span>
                            <span className="text-sm font-semibold">{score.breakdown.structuralCompleteness}/20</span>
                        </div>
                        <div className="w-full bg-slate-100 rounded-full h-2">
                            <div
                                className="bg-indigo-500 h-2 rounded-full transition-all duration-500"
                                style={{ width: `${(score.breakdown.structuralCompleteness / 20) * 100}%` }}
                            />
                        </div>
                    </div>

                    <div>
                        <div className="flex justify-between mb-2">
                            <span className="text-sm font-medium text-slate-600">Quantifiable Impact</span>
                            <span className="text-sm font-semibold">{score.breakdown.quantifiableImpact}/30</span>
                        </div>
                        <div className="w-full bg-slate-100 rounded-full h-2">
                            <div
                                className="bg-emerald-500 h-2 rounded-full transition-all duration-500"
                                style={{ width: `${(score.breakdown.quantifiableImpact / 30) * 100}%` }}
                            />
                        </div>
                    </div>

                    <div>
                        <div className="flex justify-between mb-2">
                            <span className="text-sm font-medium text-slate-600">Formatting</span>
                            <span className="text-sm font-semibold">{score.breakdown.formatting}/10</span>
                        </div>
                        <div className="w-full bg-slate-100 rounded-full h-2">
                            <div
                                className="bg-purple-500 h-2 rounded-full transition-all duration-500"
                                style={{ width: `${(score.breakdown.formatting / 10) * 100}%` }}
                            />
                        </div>
                    </div>
                </div>

                {score.suggestions.length > 0 && (
                    <div>
                        <h4 className="text-sm font-bold text-slate-800 uppercase tracking-wider mb-3">Recommendations</h4>
                        <ul className="space-y-2">
                            {score.suggestions.map((suggestion, idx) => (
                                <li key={idx} className="flex items-start text-sm text-slate-700 bg-slate-50 p-3 rounded-lg border border-slate-100">
                                    <span className="text-blue-500 mr-2 font-bold">•</span>
                                    {suggestion}
                                </li>
                            ))}
                        </ul>
                    </div>
                )}
            </div>
        </div>
    );
};

export default ATSScoreComponent;
