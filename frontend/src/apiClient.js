import axios from 'axios';

const backendApiUrl = `http://${window.location.hostname}:8000`;

const apiClient = axios.create({
  baseURL: backendApiUrl,
});

export default apiClient;