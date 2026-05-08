import React from "react";
import { DashboardSummary } from "@/types/patient";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from "recharts";

export default function CohortDistribution({ summary }: { summary: DashboardSummary }) {
  const data = Object.entries(summary.cohort_distribution).map(([name, value]) => ({
    name,
    value,
  }));

  const COLORS = ['#3B82F6', '#8B5CF6', '#EC4899', '#F43F5E', '#F59E0B', '#10B981', '#6366F1'];

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%" minHeight={256} minWidth={0}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={80}
            paddingAngle={2}
            dataKey="value"
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip 
            contentStyle={{ borderRadius: '8px', border: '1px solid #E5E7EB', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)' }}
            itemStyle={{ color: '#111827', fontSize: '14px', fontWeight: 500 }}
          />
          <Legend layout="vertical" verticalAlign="middle" align="right" wrapperStyle={{ fontSize: '12px', color: '#6B7280' }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
