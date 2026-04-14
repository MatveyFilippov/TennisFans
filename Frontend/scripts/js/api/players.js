import { apiClient } from './client.js';
export const playersApi = {
    async getAll() {
        return apiClient.get('/players');
    },
    async getById(playerId) {
        return apiClient.get(`/players/${playerId}`);
    },
    async create(data) {
        return apiClient.post('/players', data);
    },
    async edit(playerId, data) {
        return apiClient.patch(`/players/${playerId}`, data);
    },
    async delete(playerId) {
        return apiClient.delete(`/players/${playerId}`);
    },
};
