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
};
