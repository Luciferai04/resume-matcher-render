'use client';

import React from 'react';
import { SWOTAnalysis } from '@/lib/api/resume';
import { CheckCircle, AlertTriangle, Lightbulb, ShieldAlert } from 'lucide-react';

interface SWOTAnalysisProps {
    swot: SWOTAnalysis;
}

const SWOTAnalysisComponent: React.FC<SWOTAnalysisProps> = ({ swot }) => {
    return (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm mt-8">
            <div className="bg-slate-50 px-6 py-4 border-b border-slate-200">
                <h3 className="text-lg font-semibold text-slate-800">SWOT Analysis</h3>
            </div>

            <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Strengths */}
                <div className="bg-green-50 p-5 rounded-xl border border-green-100">
                    <div className="flex items-center mb-4 text-green-700">
                        <CheckCircle className="w-5 h-5 mr-2" />
                        <h4 className="font-bold text-sm uppercase tracking-wider">Strengths</h4>
                    </div>
                    <ul className="space-y-2">
                        {swot.strengths.map((item, idx) => (
                            <li key={idx} className="text-sm text-green-800 flex items-start">
                                <span className="mr-2">•</span>
                                {item}
                            </li>
                        ))}
                    </ul>
                </div>

                {/* Weaknesses */}
                <div className="bg-amber-50 p-5 rounded-xl border border-amber-100">
                    <div className="flex items-center mb-4 text-amber-700">
                        <AlertTriangle className="w-5 h-5 mr-2" />
                        <h4 className="font-bold text-sm uppercase tracking-wider">Weaknesses</h4>
                    </div>
                    <ul className="space-y-2">
                        {swot.weaknesses.map((item, idx) => (
                            <li key={idx} className="text-sm text-amber-800 flex items-start">
                                <span className="mr-2">•</span>
                                {item}
                            </li>
                        ))}
                    </ul>
                </div>

                {/* Opportunities */}
                <div className="bg-blue-50 p-5 rounded-xl border border-blue-100">
                    <div className="flex items-center mb-4 text-blue-700">
                        <Lightbulb className="w-5 h-5 mr-2" />
                        <h4 className="font-bold text-sm uppercase tracking-wider">Opportunities</h4>
                    </div>
                    <ul className="space-y-2">
                        {swot.opportunities.map((item, idx) => (
                            <li key={idx} className="text-sm text-blue-800 flex items-start">
                                <span className="mr-2">•</span>
                                {item}
                            </li>
                        ))}
                    </ul>
                </div>

                {/* Threats */}
                <div className="bg-red-50 p-5 rounded-xl border border-red-100">
                    <div className="flex items-center mb-4 text-red-700">
                        <ShieldAlert className="w-5 h-5 mr-2" />
                        <h4 className="font-bold text-sm uppercase tracking-wider">Threats</h4>
                    </div>
                    <ul className="space-y-2">
                        {swot.threats.map((item, idx) => (
                            <li key={idx} className="text-sm text-red-800 flex items-start">
                                <span className="mr-2">•</span>
                                {item}
                            </li>
                        ))}
                    </ul>
                </div>
            </div>
        </div>
    );
};

export default SWOTAnalysisComponent;
