import { apiClient } from './client.js';
export const toursApi = {
    async getAll(startedAfter, endedBefore) {
        const params = new URLSearchParams();
        if (startedAfter)
            params.append('started_after', startedAfter);
        if (endedBefore)
            params.append('ended_before', endedBefore);
        const query = params.toString();
        return apiClient.get(`/tours${query ? `?${query}` : ''}`);
    },
    async getNotEnded() {
        return apiClient.get('/tours/not_ended');
    },
    async getById(tourId) {
        return apiClient.get(`/tours/${tourId}`);
    },
    async create(data) {
        return apiClient.post('/tours', data);
    },
    async edit(tourId, data) {
        return apiClient.patch(`/tours/${tourId}`, data);
    },
    async delete(tourId) {
        return apiClient.delete(`/tours/${tourId}`);
    },
    async getPlayersPoints(tourId) {
        return apiClient.get(`/tours/${tourId}/players_points`);
    },
    async getProposedPairs(tourId) {
        return apiClient.get(`/tours/${tourId}/propose_players_pairs`);
    },
};
