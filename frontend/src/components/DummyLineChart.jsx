import React, { useEffect, useRef } from 'react';
import * as d3 from 'd3';

const DummyLineChart = ({ data }) => {
  const svgRef = useRef();
  const containerRef = useRef();

  useEffect(() => {
    const renderChart = () => {
      if (!containerRef.current || !data || data.length === 0) return;

      d3.select(svgRef.current).selectAll('*').remove();

      const containerWidth = containerRef.current.offsetWidth;
      const containerHeight = 350;

      const margin = { top: 20, right: 40, bottom: 40, left: 50 };
      const width = containerWidth - margin.left - margin.right;
      const height = containerHeight - margin.top - margin.bottom;

      const svg = d3.select(svgRef.current)
        .attr("width", containerWidth)
        .attr("height", containerHeight)
        .append("g")
        .attr("transform", `translate(${margin.left},${margin.top})`);

      // Create a clean copy of the data, parsing it correctly
      const parsedData = data.map(d => ({
        date: d3.timeParse("%Y-%m-%d")(d.date),
        sessions: +d.sessions,
        impressions: +d.impressions
      }));

      const xScale = d3.scaleTime().domain(d3.extent(parsedData, d => d.date)).range([0, width]);
      const yScale = d3.scaleLinear().domain([0, d3.max(parsedData, d => Math.max(d.sessions, d.impressions)) * 1.1]).range([height, 0]);

      svg.append("g").attr("transform", `translate(0,${height})`).call(d3.axisBottom(xScale).ticks(5).tickFormat(d3.timeFormat("%b %d")));
      svg.append("g").call(d3.axisLeft(yScale));

      const lineSessions = d3.line().x(d => xScale(d.date)).y(d => yScale(d.sessions));
      const lineImpressions = d3.line().x(d => xScale(d.date)).y(d => yScale(d.impressions));

      svg.append("path").datum(parsedData).attr("fill", "none").attr("stroke", "#4f46e5").attr("stroke-width", 2).attr("d", lineSessions);
      svg.append("path").datum(parsedData).attr("fill", "none").attr("stroke", "#10b981").attr("stroke-width", 2).attr("d", lineImpressions);
    };

    renderChart();
    window.addEventListener('resize', renderChart);
    return () => window.removeEventListener('resize', renderChart);
  }, [data]);

  return (
    <div ref={containerRef} className="w-full h-full">
      <svg ref={svgRef}></svg>
    </div>
  );
};

export default DummyLineChart;
// import React, { useEffect, useRef } from 'react';
// import * as d3 from 'd3';

// const DummyLineChart = ({ data }) => {
//   const svgRef = useRef();
//   const containerRef = useRef();

//   useEffect(() => {
//     const renderChart = () => {
//       if (!containerRef.current || !data || data.length === 0) return;

//       d3.select(svgRef.current).selectAll('*').remove();

//       const containerWidth = containerRef.current.offsetWidth;
//       const containerHeight = 350;

//       const margin = { top: 20, right: 40, bottom: 40, left: 50 };
//       const width = containerWidth - margin.left - margin.right;
//       const height = containerHeight - margin.top - margin.bottom;

//       const svg = d3.select(svgRef.current)
//         .attr("width", containerWidth)
//         .attr("height", containerHeight)
//         .append("g")
//         .attr("transform", `translate(${margin.left},${margin.top})`);

//       const parseDate = d3.timeParse("%Y-%m-%d");
//       data.forEach(d => {
//         d.date = parseDate(d.date);
//         d.sessions = +d.sessions;
//         d.impressions = +d.impressions;
//       });

//       const xScale = d3.scaleTime().domain(d3.extent(data, d => d.date)).range([0, width]);
//       const yScale = d3.scaleLinear().domain([0, d3.max(data, d => Math.max(d.sessions, d.impressions)) * 1.1]).range([height, 0]);

//       svg.append("g").attr("transform", `translate(0,${height})`).call(d3.axisBottom(xScale).ticks(5).tickFormat(d3.timeFormat("%b %d")));
//       svg.append("g").call(d3.axisLeft(yScale));

//       const lineSessions = d3.line().x(d => xScale(d.date)).y(d => yScale(d.sessions));
//       const lineImpressions = d3.line().x(d => xScale(d.date)).y(d => yScale(d.impressions));

//       svg.append("path").datum(data).attr("fill", "none").attr("stroke", "#4f46e5").attr("stroke-width", 2).attr("d", lineSessions);
//       svg.append("path").datum(data).attr("fill", "none").attr("stroke", "#10b981").attr("stroke-width", 2).attr("d", lineImpressions);
//     };

//     renderChart();
//     window.addEventListener('resize', renderChart);
//     return () => window.removeEventListener('resize', renderChart);
//   }, [data]);

//   return (
//     <div ref={containerRef} className="w-full h-full">
//       <svg ref={svgRef}></svg>
//     </div>
//   );
// };

// export default DummyLineChart;