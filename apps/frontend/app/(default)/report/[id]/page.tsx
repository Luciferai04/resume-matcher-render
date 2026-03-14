'use client';

import React, { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { apiFetch, API_BASE } from '@/lib/api/client';

/* ─── Types ───────────────────────────────────────────────────────────── */

interface FunnelStage { stage: string; count: number; pct: number; }
interface ScoreGrowth {
    average_initial_score: number | null;
    average_improved_score: number | null;
    total_scored: number;
    total_improved: number;
    score_distribution: {
        excellent_90_plus: number;
        good_75_89: number;
        average_50_74: number;
        needs_work_below_50: number;
    };
}
interface TopPerformer { name: string; user_id: string; ats_score: number; tailored_count: number; status: string; }
interface SkillGap { skill: string; students_affected: number; }
interface ReportData {
    cohort: { name: string; cohort_id: string; created_at: string };
    generated_at: string;
    summary: { total_students: number; engagement_rate: number; completion_rate: number; };
    funnel: FunnelStage[];
    score_growth: ScoreGrowth;
    top_performers: TopPerformer[];
    all_results: TopPerformer[];
    skill_gaps: SkillGap[];
}

/* ─── Swiss Tokens ────────────────────────────────────────────────────── */

const CANVAS = '#f0f0e8';
const INK = '#000000';
const BLUE = '#1d4ed8';
const PANEL = '#e5e5e0';
const GREEN = '#15803d';
const RED = '#dc2626';
const ORANGE = '#f97316';
const MUTED = '#6b7280';

const FONT_MONO = "'Space Grotesk', 'Geist Mono', monospace";
const FONT_SANS = "'Geist Sans', 'Geist', sans-serif";
const SHADOW = '4px 4px 0px 0px #000';
const SHADOW_SM = '2px 2px 0px 0px #000';

const FUNNEL_COLORS = [BLUE, '#7c3aed', ORANGE, GREEN];

/* ─── Components ──────────────────────────────────────────────────────── */

function SwissCard({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
    return (
        <div style={{ background: CANVAS, border: `2px solid ${INK}`, boxShadow: SHADOW, ...style }}>
            {children}
        </div>
    );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
    return (
        <h2 style={{
            fontFamily: FONT_MONO, fontSize: '12px', fontWeight: 700,
            textTransform: 'uppercase', letterSpacing: '0.12em',
            color: INK, marginBottom: '20px', borderBottom: `2px solid ${INK}`,
            paddingBottom: '8px',
        }}>
            {children}
        </h2>
    );
}

/* ─── Main Page ───────────────────────────────────────────────────────── */

export default function ReportPage() {
    const params = useParams();
    const id = params?.id as string;
    const [report, setReport] = useState<ReportData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!id) return;
        (async () => {
            try {
                const res = await apiFetch(`/admin/cohorts/${id}/report`);
                if (!res.ok) throw new Error(`Failed to load report (${res.status})`);
                setReport(await res.json());
            } catch (e: any) { setError(e.message); }
            finally { setLoading(false); }
        })();
    }, [id]);

    if (loading) return (
        <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: CANVAS, fontFamily: FONT_MONO, fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.1em', color: MUTED }}>
            Loading Report...
        </div>
    );

    if (error || !report) return (
        <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: CANVAS, fontFamily: FONT_MONO, fontSize: '12px', textTransform: 'uppercase', color: RED }}>
            {error || 'Report not found'}
        </div>
    );

    const { cohort, summary, funnel, score_growth, top_performers, all_results, skill_gaps } = report;

    return (
        <div style={{ minHeight: '100vh', background: CANVAS, fontFamily: FONT_SANS }}>
            {/* Print Button */}
            <div className="no-print" style={{ position: 'fixed', top: '16px', right: '16px', zIndex: 100, display: 'flex', gap: '6px' }}>
                <button onClick={() => window.print()} style={{
                    fontFamily: FONT_MONO, fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em',
                    background: INK, color: '#fff', border: `2px solid ${INK}`, boxShadow: SHADOW_SM, padding: '8px 16px', cursor: 'pointer',
                }}>
                    ↓ Save as PDF
                </button>
                <a href="/admin" style={{
                    fontFamily: FONT_MONO, fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em',
                    background: CANVAS, color: INK, border: `2px solid ${INK}`, boxShadow: SHADOW_SM, padding: '8px 16px', textDecoration: 'none',
                }}>
                    ← Admin
                </a>
            </div>

            {/* Header */}
            <div style={{ background: INK, padding: '40px 60px 36px', borderBottom: `4px solid ${BLUE}` }}>
                <div style={{ maxWidth: '960px', margin: '0 auto' }}>
                    <div style={{ fontFamily: FONT_MONO, fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.15em', color: '#999', marginBottom: '8px' }}>
            // Executive Report
                    </div>
                    <h1 style={{ fontFamily: FONT_MONO, fontSize: '28px', fontWeight: 800, color: '#fff', textTransform: 'uppercase', letterSpacing: '0.05em', margin: 0 }}>
                        {cohort.name}
                    </h1>
                    <p style={{ fontFamily: FONT_MONO, fontSize: '11px', color: '#777', margin: '6px 0 0 0', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        ATS Journey Report — {new Date(report.generated_at).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}
                    </p>

                    {/* Summary pills */}
                    <div style={{ display: 'flex', gap: '12px', marginTop: '24px', flexWrap: 'wrap' }}>
                        {[
                            { label: 'Students', value: summary.total_students, color: BLUE },
                            { label: 'Engagement', value: `${summary.engagement_rate}%`, color: ORANGE },
                            { label: 'Completion', value: `${summary.completion_rate}%`, color: GREEN },
                        ].map(p => (
                            <div key={p.label} style={{
                                border: `2px solid ${p.color}`, padding: '12px 20px', background: 'transparent',
                            }}>
                                <div style={{ fontFamily: FONT_MONO, fontSize: '24px', fontWeight: 800, color: p.color }}>{p.value}</div>
                                <div style={{ fontFamily: FONT_MONO, fontSize: '9px', color: '#999', textTransform: 'uppercase', letterSpacing: '0.1em', marginTop: '2px' }}>{p.label}</div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            <div style={{ maxWidth: '960px', margin: '0 auto', padding: '40px 60px 80px' }}>
                {/* Funnel */}
                <section style={{ marginBottom: '48px' }}>
                    <SectionTitle>// Student Journey Funnel</SectionTitle>
                    <SwissCard style={{ padding: '28px', display: 'flex', gap: '0' }}>
                        {funnel.map((stage, i) => (
                            <React.Fragment key={stage.stage}>
                                <div style={{ flex: 1, textAlign: 'center', padding: '0 12px' }}>
                                    <div style={{ fontFamily: FONT_SANS, fontSize: '36px', fontWeight: 800, color: FUNNEL_COLORS[i], lineHeight: 1 }}>
                                        {stage.count}
                                    </div>
                                    <div style={{ fontFamily: FONT_MONO, fontSize: '10px', color: MUTED, textTransform: 'uppercase', letterSpacing: '0.08em', marginTop: '4px', marginBottom: '12px' }}>
                                        {stage.stage}
                                    </div>
                                    <div style={{ height: '6px', background: PANEL, border: `1px solid ${INK}` }}>
                                        <div style={{ width: `${stage.pct}%`, height: '100%', background: FUNNEL_COLORS[i], transition: 'width 1s ease' }} />
                                    </div>
                                    <div style={{ fontFamily: FONT_MONO, fontSize: '11px', color: FUNNEL_COLORS[i], fontWeight: 700, marginTop: '4px' }}>{stage.pct}%</div>
                                </div>
                                {i < funnel.length - 1 && (
                                    <div style={{ display: 'flex', alignItems: 'center', color: PANEL, fontSize: '18px', fontFamily: FONT_MONO, fontWeight: 700, paddingTop: '10px' }}>→</div>
                                )}
                            </React.Fragment>
                        ))}
                    </SwissCard>
                </section>

                {/* Score Growth */}
                <section style={{ marginBottom: '48px' }}>
                    <SectionTitle>// ATS Score Overview</SectionTitle>
                    <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                        {/* Scores */}
                        <SwissCard style={{ padding: '32px', display: 'flex', gap: '40px', alignItems: 'center', justifyContent: 'center', flex: '1 1 300px' }}>
                            <div style={{ textAlign: 'center' }}>
                                <div style={{ fontFamily: FONT_SANS, fontSize: '56px', fontWeight: 800, color: BLUE, lineHeight: 1 }}>
                                    {score_growth.average_initial_score ?? '—'}
                                </div>
                                <div style={{ fontFamily: FONT_MONO, fontSize: '10px', color: MUTED, textTransform: 'uppercase', letterSpacing: '0.1em', marginTop: '6px' }}>
                                    Avg Score
                                </div>
                            </div>
                            {score_growth.average_improved_score !== null && (
                                <>
                                    <div style={{ fontFamily: FONT_MONO, fontSize: '24px', color: PANEL, fontWeight: 700 }}>→</div>
                                    <div style={{ textAlign: 'center' }}>
                                        <div style={{ fontFamily: FONT_SANS, fontSize: '56px', fontWeight: 800, color: GREEN, lineHeight: 1 }}>
                                            {score_growth.average_improved_score}
                                        </div>
                                        <div style={{ fontFamily: FONT_MONO, fontSize: '10px', color: MUTED, textTransform: 'uppercase', letterSpacing: '0.1em', marginTop: '6px' }}>
                                            After Improvement
                                        </div>
                                    </div>
                                </>
                            )}
                        </SwissCard>

                        {/* Distribution */}
                        <SwissCard style={{ padding: '28px', flex: '1 1 260px' }}>
                            <div style={{ fontFamily: FONT_MONO, fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '16px' }}>
                                Score Distribution
                            </div>
                            {[
                                { label: 'Excellent (90+)', count: score_growth.score_distribution.excellent_90_plus, color: GREEN },
                                { label: 'Good (75–89)', count: score_growth.score_distribution.good_75_89, color: BLUE },
                                { label: 'Average (50–74)', count: score_growth.score_distribution.average_50_74, color: ORANGE },
                                { label: 'Needs Work (<50)', count: score_growth.score_distribution.needs_work_below_50, color: RED },
                            ].map(d => (
                                <div key={d.label} style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                                    <div style={{ width: '10px', height: '10px', background: d.color, border: `1px solid ${INK}`, flexShrink: 0 }} />
                                    <div style={{ flex: 1, fontFamily: FONT_MONO, fontSize: '11px', color: MUTED }}>{d.label}</div>
                                    <div style={{ fontFamily: FONT_MONO, fontWeight: 800, fontSize: '18px', color: INK }}>{d.count}</div>
                                </div>
                            ))}
                        </SwissCard>
                    </div>
                </section>

                {/* Top Performers */}
                <section style={{ marginBottom: '48px' }}>
                    <SectionTitle>// Top Performers</SectionTitle>
                    <SwissCard style={{ overflow: 'hidden' }}>
                        {top_performers.length === 0 ? (
                            <div style={{ padding: '40px', textAlign: 'center', fontFamily: FONT_MONO, fontSize: '11px', color: MUTED, textTransform: 'uppercase' }}>
                                No scored students yet
                            </div>
                        ) : top_performers.map((p, i) => (
                            <div key={p.user_id} style={{
                                display: 'flex', alignItems: 'center', padding: '14px 24px',
                                borderBottom: i < top_performers.length - 1 ? `1px solid ${PANEL}` : 'none',
                                background: i === 0 ? '#fefce8' : i === 1 ? PANEL : i === 2 ? '#fff7ed' : CANVAS,
                            }}>
                                <div style={{
                                    width: '32px', height: '32px', border: `2px solid ${INK}`,
                                    background: i === 0 ? BLUE : i === 1 ? INK : i === 2 ? '#92400e' : PANEL,
                                    color: i < 3 ? '#fff' : INK,
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    fontFamily: FONT_MONO, fontWeight: 800, fontSize: '13px', marginRight: '16px', flexShrink: 0,
                                }}>
                                    {i + 1}
                                </div>
                                <div style={{ flex: 1, fontFamily: FONT_SANS, fontWeight: 700, color: INK, fontSize: '14px' }}>{p.name}</div>
                                <div style={{
                                    fontFamily: FONT_MONO, fontWeight: 800, fontSize: '28px',
                                    color: p.ats_score >= 90 ? GREEN : p.ats_score >= 75 ? BLUE : p.ats_score >= 50 ? ORANGE : RED,
                                }}>
                                    {p.ats_score}
                                </div>
                            </div>
                        ))}
                    </SwissCard>
                </section>

                {/* Skill Gaps */}
                {skill_gaps.length > 0 && (
                    <section style={{ marginBottom: '48px' }}>
                        <SectionTitle>// Common Skill Gaps</SectionTitle>
                        <SwissCard style={{ padding: '28px' }}>
                            {skill_gaps.map(gap => {
                                const barPct = Math.round((gap.students_affected / summary.total_students) * 100);
                                return (
                                    <div key={gap.skill} style={{ marginBottom: '14px' }}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                                            <span style={{ fontFamily: FONT_SANS, fontSize: '13px', fontWeight: 600, color: INK }}>{gap.skill}</span>
                                            <span style={{ fontFamily: FONT_MONO, fontSize: '11px', color: RED, fontWeight: 700 }}>{gap.students_affected} students</span>
                                        </div>
                                        <div style={{ height: '6px', background: PANEL, border: `1px solid ${INK}` }}>
                                            <div style={{ width: `${barPct}%`, height: '100%', background: RED, transition: 'width 1s ease' }} />
                                        </div>
                                    </div>
                                );
                            })}
                        </SwissCard>
                    </section>
                )}

                {/* Full Results Table */}
                <section style={{ marginBottom: '48px', breakBefore: 'page' }}>
                    <SectionTitle>// Full Student Results</SectionTitle>
                    <SwissCard style={{ overflow: 'hidden' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: FONT_SANS }}>
                            <thead>
                                <tr style={{ background: PANEL, borderBottom: `2px solid ${INK}` }}>
                                    <th style={{ padding: '12px', textAlign: 'left', fontFamily: FONT_MONO, fontSize: '10px', textTransform: 'uppercase' }}>Rank</th>
                                    <th style={{ padding: '12px', textAlign: 'left', fontFamily: FONT_MONO, fontSize: '10px', textTransform: 'uppercase' }}>Name</th>
                                    <th style={{ padding: '12px', textAlign: 'center', fontFamily: FONT_MONO, fontSize: '10px', textTransform: 'uppercase' }}>Score</th>
                                    <th style={{ padding: '12px', textAlign: 'center', fontFamily: FONT_MONO, fontSize: '10px', textTransform: 'uppercase' }}>Tailored</th>
                                    <th style={{ padding: '12px', textAlign: 'right', fontFamily: FONT_MONO, fontSize: '10px', textTransform: 'uppercase' }}>Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                {all_results.map((p, i) => (
                                    <tr key={p.user_id} style={{ borderBottom: `1px solid ${PANEL}` }}>
                                        <td style={{ padding: '12px', fontFamily: FONT_MONO, fontSize: '12px', fontWeight: 700 }}>{i + 1}</td>
                                        <td style={{ padding: '12px', fontSize: '13px', fontWeight: 600 }}>{p.name}</td>
                                        <td style={{ padding: '12px', textAlign: 'center' }}>
                                            <span style={{
                                                padding: '2px 8px', border: `1px solid ${INK}`, fontWeight: 800, fontFamily: FONT_MONO,
                                                color: p.ats_score >= 90 ? GREEN : p.ats_score >= 75 ? BLUE : p.ats_score >= 50 ? ORANGE : RED,
                                            }}>
                                                {p.ats_score}
                                            </span>
                                        </td>
                                        <td style={{ padding: '12px', textAlign: 'center', fontFamily: FONT_MONO, fontSize: '12px' }}>{p.tailored_count}</td>
                                        <td style={{ padding: '12px', textAlign: 'right', fontFamily: FONT_MONO, fontSize: '9px', textTransform: 'uppercase', color: MUTED }}>
                                            {p.status.replace('_', ' ')}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </SwissCard>
                </section>

                {/* Footer */}
                <div style={{
                    fontFamily: FONT_MONO, fontSize: '10px', color: MUTED,
                    textTransform: 'uppercase', letterSpacing: '0.08em',
                    borderTop: `2px solid ${INK}`, paddingTop: '16px', textAlign: 'center',
                }}>
                    Resume Matcher — AI-Powered ATS Journey Report • {new Date(report.generated_at).toLocaleString()}
                </div>
            </div>

            <style>{`
        @media print {
          .no-print { display: none !important; }
          body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
          @page { margin: 0.5in; size: A4; }
        }
      `}</style>
        </div>
    );
}
