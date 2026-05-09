import React from "react";
import { DashboardSummary } from "@/types/patient";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";

export default function ConversionFunnel({ summary }: { summary: DashboardSummary }) {
  const funnel = summary.conversion_funnel;
  
  // Create data array from funnel metrics
  const data = [
    { name: 'Pending', count: funnel?.pending || 0 },
    { name: 'In Progress', count: funnel?.interested || 0 },
    { name: 'Converted', count: funnel?.converted || 0 },
    { name: 'Declined', count: funnel?.declined || 0 },
  ];

  const COLORS = ['#F59E0B', '#3B82F6', '#10B981', '#F43F5E'];

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%" minHeight={256} minWidth={0}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#F3F4F6" />
          <XAxis type="number" hide />
          <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} tick={{ fill: '#6B7280', fontSize: 12 }} width={80} />
          <Tooltip 
            cursor={{ fill: '#F9FAFB' }}
            contentStyle={{ borderRadius: '8px', border: '1px solid #E5E7EB', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)' }}
          />
          <Bar dataKey="count" radius={[0, 4, 4, 0]} barSize={24}>
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
