/**
 * Custom Plot component using plotly.js-dist-min (2.x) instead of plotly.js (3.x).
 * react-plotly.js 2.6.0 was designed for Plotly 2.x API; using 3.x causes
 * axis scaling and rendering incompatibilities.
 */
import Plotly from 'plotly.js-dist-min'
import createPlotlyComponent from 'react-plotly.js/factory'

const Plot = createPlotlyComponent(Plotly as any)

export default Plot
