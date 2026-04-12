import { apiClient } from './client.js';
import { PlayerResponse, CreatePlayerRequest } from '../types/index.js';

export const playersApi = {
    async getAll(): Promise<PlayerResponse[]> {
        return apiClient.get<PlayerResponse[]>('/players');
    },

    async getById(playerId: number): Promise<PlayerResponse> {
        return apiClient.get<PlayerResponse>(`/players/${playerId}`);
    },

    async create(data: CreatePlayerRequest): Promise<PlayerResponse> {
        return apiClient.post<PlayerResponse>('/players', data);
    },
};