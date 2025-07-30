import React, { useEffect, useRef } from 'react';
import * as d3 from 'd3';

const EnhancedLineChart = ({ data }) => {
  const svgRef = useRef();
  const containerRef = useRef();

  useEffect(() => {
    const renderChart = () => {
      if (!containerRef.current || !data || data.length === 0) return;

      d3.select(svgRef.current).selectAll('*').remove();
      d3.select("body").selectAll(".d3-tooltip").remove();

      const containerWidth = containerRef.current.offsetWidth;
      const containerHeight = 350;
      const margin = { top: 20, right: 20, bottom: 50, left: 60 };
      const width = containerWidth - margin.left - margin.right;
      const height = containerHeight - margin.top - margin.bottom;

      const svg = d3.select(svgRef.current)
        .attr("width", containerWidth)
        .attr("height", containerHeight)
        .append("g")
        .attr("transform", `translate(${margin.left},${margin.top})`);

      const parsedData = data.map(d => ({
        date: d3.timeParse("%Y-%m-%d")(d.date),
        sessions: +d.sessions,
        impressions: +d.impressions
      })).sort((a, b) => a.date - b.date);

      const xScale = d3.scaleTime().domain(d3.extent(parsedData, d => d.date)).range([0, width]);
      const yScale = d3.scaleLinear().domain([0, d3.max(parsedData, d => d.impressions) * 1.15]).range([height, 0]);

      svg.append("g").attr("transform", `translate(0,${height})`).call(d3.axisBottom(xScale).ticks(5).tickFormat(d3.timeFormat("%b %d")));
      svg.append("g").call(d3.axisLeft(yScale));

      // Add Y-axis label
      svg.append("text")
        .attr("transform", "rotate(-90)")
        .attr("y", 0 - margin.left + 15) // Corrected position
        .attr("x", 0 - (height / 2))
        .attr("dy", "1em")
        .style("text-anchor", "middle")
        .style("font-weight", "bold")
        .style("fill", "#374151")
        .text("Count");
        
      // Add X-axis label
      svg.append("text")
        .attr("y", height + margin.bottom - 10)
        .attr("x", width / 2)
        .style("text-anchor", "middle")
        .style("font-weight", "bold")
        .style("fill", "#374151")
        .text("Date");

      const lineSessions = d3.line().curve(d3.curveMonotoneX).x(d => xScale(d.date)).y(d => yScale(d.sessions));
      const lineImpressions = d3.line().curve(d3.curveMonotoneX).x(d => xScale(d.date)).y(d => yScale(d.impressions));

      svg.append("path").datum(parsedData).attr("fill", "none").attr("stroke", "#4f46e5").attr("stroke-width", 2.5).attr("d", lineSessions);
      svg.append("path").datum(parsedData).attr("fill", "none").attr("stroke", "#10b981").attr("stroke-width", 2.5).attr("d", lineImpressions);
      
      // Add a legend
      const legendData = [
        { name: "Sessions", color: "#4f46e5" },
        { name: "Impressions", color: "#10b981" }
      ];

      const legend = svg.selectAll(".legend")
        .data(legendData)
        .enter().append("g")
        .attr("class", "legend")
        .attr("transform", (d, i) => `translate(${i * 120}, -15)`); // Corrected position

      legend.append("rect")
        .attr("x", 0)
        .attr("width", 12)
        .attr("height", 12)
        .style("fill", d => d.color);

      legend.append("text")
        .attr("x", 18)
        .attr("y", 6)
        .attr("dy", ".35em")
        .style("text-anchor", "start")
        .text(d => d.name);
    };
    
    renderChart();
    window.addEventListener('resize', renderChart);
    return () => window.removeEventListener('resize', renderChart);
  }, [data]);

  return <div ref={containerRef} className="w-full h-full"><svg ref={svgRef}></svg></div>;
};

export default EnhancedLineChart;
// // src/components/EnhancedLineChart.jsx
// import React, { useEffect, useRef } from 'react';
// import * as d3 from 'd3';

// const EnhancedLineChart = ({ data }) => {
//   const svgRef = useRef();
//   const containerRef = useRef();

//   useEffect(() => {
//     const renderChart = () => {
//         if (!containerRef.current || !data || data.length === 0) return;

//         d3.select(svgRef.current).selectAll('*').remove();
//         d3.select("body").selectAll(".d3-tooltip").remove();

//         const containerWidth = containerRef.current.offsetWidth;
//         const containerHeight = 350;
//         const margin = { top: 30, right: 60, bottom: 50, left: 70 };
//         const width = containerWidth - margin.left - margin.right;
//         const height = containerHeight - margin.top - margin.bottom;

//         const svg = d3.select(svgRef.current)
//             .attr("width", containerWidth).attr("height", containerHeight)
//             .append("g").attr("transform", `translate(${margin.left},${margin.top})`);

//         const parsedData = data.map(d => ({
//             date: d3.timeParse("%Y-%m-%d")(d.date),
//             sessions: +d.sessions,
//             impressions: +d.impressions
//         })).sort((a, b) => a.date - b.date);

//         const xScale = d3.scaleTime().domain(d3.extent(parsedData, d => d.date)).range([0, width]);
//         const yScale = d3.scaleLinear().domain([0, d3.max(parsedData, d => d.impressions) * 1.15]).range([height, 0]);

//         svg.append("g").attr("transform", `translate(0,${height})`).call(d3.axisBottom(xScale).ticks(5).tickFormat(d3.timeFormat("%b %d"))).attr("font-size", "12px").attr("color", "#4b5563");
//         svg.append("g").call(d3.axisLeft(yScale)).attr("font-size", "12px").attr("color", "#4b5563");

//         const area = (yValue) => d3.area().x(d => xScale(d.date)).y0(height).y1(d => yScale(d[yValue]));
//         const line = (yValue) => d3.line().curve(d3.curveMonotoneX).x(d => xScale(d.date)).y(d => yScale(d[yValue]));
        
//         const gradients = [
//             { id: "gradientSessions", color: "#4f46e5" },
//             { id: "gradientImpressions", color: "#10b981" }
//         ];

//         svg.append("defs").selectAll("linearGradient").data(gradients).enter().append("linearGradient")
//             .attr("id", d => d.id).attr("x1", "0%").attr("y1", "0%").attr("x2", "0%").attr("y2", "100%")
//             .selectAll("stop").data(d => [{ offset: "0%", color: d.color, opacity: 0.8 }, { offset: "100%", color: d.color, opacity: 0.1 }])
//             .enter().append("stop").attr("offset", d => d.offset).attr("stop-color", d => d.color).attr("stop-opacity", d => d.opacity);
        
//         svg.append("path").datum(parsedData).attr("fill", "url(#gradientSessions)").attr("d", area("sessions"));
//         svg.append("path").datum(parsedData).attr("fill", "url(#gradientImpressions)").attr("d", area("impressions"));

//         svg.append("path").datum(parsedData).attr("fill", "none").attr("stroke", "#4f46e5").attr("stroke-width", 3).attr("d", line("sessions"));
//         svg.append("path").datum(parsedData).attr("fill", "none").attr("stroke", "#10b981").attr("stroke-width", 3).attr("d", line("impressions"));

//         const tooltip = d3.select("body").append("div").attr("class", "d3-tooltip bg-white p-2 rounded-lg shadow-lg border text-sm")
//             .style("position", "absolute").style("opacity", 0).style("pointer-events", "none");

//         svg.append("rect").attr("width", width).attr("height", height).attr("fill", "none").attr("pointer-events", "all")
//             .on("mouseover", () => tooltip.style("opacity", 1)).on("mouseout", () => tooltip.style("opacity", 0))
//             .on("mousemove", event => {
//                 const [xPos] = d3.pointer(event);
//                 const date = xScale.invert(xPos);
//                 const bisect = d3.bisector(d => d.date).left;
//                 const i = bisect(parsedData, date, 1);
//                 const d = date - parsedData[i - 1].date > parsedData[i].date - date ? parsedData[i] : parsedData[i - 1];
//                 tooltip.html(`<div class="font-bold">${d3.timeFormat("%b %d, %Y")(d.date)}</div><div>Sessions: ${d.sessions}</div><div>Impressions: ${d.impressions}</div>`)
//                     .style("left", (event.pageX + 20) + "px").style("top", (event.pageY - 60) + "px");
//             });
//     };

//     renderChart();
//     window.addEventListener('resize', renderChart);
//     return () => {
//         window.removeEventListener('resize', renderChart);
//         d3.select("body").selectAll(".d3-tooltip").remove();
//     };
//   }, [data]);

//   return <div ref={containerRef} className="w-full h-full"><svg ref={svgRef}></svg></div>;
// };

// export default EnhancedLineChart;