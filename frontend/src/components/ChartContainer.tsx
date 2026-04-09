import React from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  Cell
} from 'recharts';
import type { ChartConfig } from '../api/client';

interface ChartContainerProps {
  config: ChartConfig;
}

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884d8', '#82ca9d'];

const ChartContainer: React.FC<ChartContainerProps> = ({ config }) => {
  const { type, chart_type, x_axis, y_axis, data } = config;
  const initialViewMode = type === 'table' ? 'table' : 'chart';
  const [viewMode, setViewMode] = React.useState<'table' | 'chart'>(initialViewMode);
  
  // The actual chart type (if we toggle to chart view)
  const activeChartType = chart_type || (type !== 'table' ? type : 'bar');

  if (!data || data.length === 0) {
    return <div className="chart-placeholder">No data available for visualization</div>;
  }

  const renderTable = () => (
    <div className="table-preview-container">
       <table className="preview-table">
          <thead>
              <tr>
                  {Object.keys(data[0] || {}).map(k => <th key={k}>{k}</th>)}
              </tr>
          </thead>
          <tbody>
              {data.slice(0, 100).map((row, i) => (
                  <tr key={i}>
                      {Object.values(row).map((v: any, j) => <td key={j}>{String(v)}</td>)}
                  </tr>
              ))}
          </tbody>
       </table>
    </div>
  );

  const renderVisualChart = () => {
    // Requirement 4: Transform data into a standard name/value format
    // name = x_axis value, value = y_axis value
    const chartData = data.map(row => ({
      ...row,
      name: String(row[x_axis!] ?? 'N/A'),
      value: typeof row[y_axis!] === 'number' ? row[y_axis!] : parseFloat(row[y_axis!] || '0')
    }));

    // Requirement 8: Debug Logging
    console.log('[ChartContainer] Rendering Chart:', { 
      type: activeChartType,
      x: x_axis, 
      y: y_axis,
      rows: chartData.length,
      firstRow: chartData[0]
    });

    switch (activeChartType) {
      case 'line':
        return (
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line 
              type="monotone" 
              dataKey="value" 
              stroke="#8884d8" 
              name={y_axis || 'Value'} 
              activeDot={{ r: 8 }} 
              strokeWidth={2}
            />
          </LineChart>
        );
      case 'pie':
        return (
          <PieChart>
            <Pie
              data={chartData}
              cx="50%"
              cy="50%"
              labelLine={true}
              label={({ name, percent }: { name: string; percent: number }) => `${name} (${(percent * 100).toFixed(0)}%)`}
              outerRadius={80}
              fill="#8884d8"
              dataKey="value"
              nameKey="name"
            >
              {chartData.map((_, index) => (
                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip />
            <Legend />
          </PieChart>
        );
      case 'bar':
      default:
        return (
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey="value" fill="#82ca9d" name={y_axis || 'Value'} radius={[4, 4, 0, 0]} />
          </BarChart>
        );
    }
  };

  return (
    <div className="chart-wrapper">
      <div className="chart-toggle-header" style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '8px' }}>
        <div className="toggle-group" style={{ display: 'inline-flex', borderRadius: '6px', overflow: 'hidden', border: '1px solid var(--border-color)', backgroundColor: 'var(--surface-color)' }}>
          <button 
            className={`toggle-btn ${viewMode === 'table' ? 'active' : ''}`}
            onClick={() => setViewMode('table')}
            style={{ padding: '4px 12px', fontSize: '0.8rem', border: 'none', cursor: 'pointer', background: viewMode === 'table' ? 'var(--primary-color)' : 'transparent', color: viewMode === 'table' ? 'white' : 'var(--text-color)' }}
          >
            📄 Table
          </button>
          <button 
            className={`toggle-btn ${viewMode === 'chart' ? 'active' : ''}`}
            onClick={() => setViewMode('chart')}
            style={{ padding: '4px 12px', fontSize: '0.8rem', border: 'none', borderLeft: '1px solid var(--border-color)', cursor: 'pointer', background: viewMode === 'chart' ? 'var(--primary-color)' : 'transparent', color: viewMode === 'chart' ? 'white' : 'var(--text-color)' }}
          >
            📊 Chart
          </button>
        </div>
      </div>
      <div className="chart-container" style={{ width: '100%', height: viewMode === 'chart' ? 300 : 'auto', maxHeight: 400, overflowY: viewMode === 'table' ? 'auto' : 'visible' }}>
        {viewMode === 'chart' ? (
          <ResponsiveContainer width="100%" height="100%">
            {renderVisualChart()}
          </ResponsiveContainer>
        ) : (
          renderTable()
        )}
      </div>
    </div>
  );
};

export default ChartContainer;
