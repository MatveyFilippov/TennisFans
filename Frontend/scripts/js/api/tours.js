import { apiClient } from './client.js';
export const toursApi = {
    async getAll() {
        return apiClient.get('/tours');
    },
    async getNotEnded() {
        return apiClient.get('/tours/not_ended');
    },
    async getEnded(startDate, endDate) {
        const params = new URLSearchParams();
        if (startDate)
            params.append('start_date', startDate);
        if (endDate)
            params.append('end_date', endDate);
        const query = params.toString();
        return apiClient.get(`/tours/ended${query ? `?${query}` : ''}`);
    },
    async getById(tourId) {
        return apiClient.get(`/tours/${tourId}`);
    },
    async start(data) {
        return apiClient.post('/tours', data);
    },
    async end(tourId, data) {
        return apiClient.put(`/tours/${tourId}/end`, data);
    },
    async getPlayersPoints(tourId) {
        return apiClient.get(`/tours/${tourId}/players_points`);
    },
};
