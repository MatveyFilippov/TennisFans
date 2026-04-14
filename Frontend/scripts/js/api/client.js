const API_BASE_URL = 'http://localhost:8000/api';
class ApiClient {
    async request(endpoint, options = {}) {
        const url = `${API_BASE_URL}${endpoint}`;
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers,
        };
        try {
            const response = await fetch(url, {
                ...options,
                headers,
            });
            if (!response.ok) {
                if (response.status === 422) {
                    const errorData = await response.json();
                    throw new Error(`Validation Error: ${JSON.stringify(errorData.detail)}`);
                }
                throw new Error(`HTTP Error: ${response.status} ${response.statusText}`);
            }
            if (response.status === 204) {
                return null;
            }
            return await response.json();
        }
        catch (error) {
            console.error('API Request Failed:', error);
            throw error;
        }
    }
    async get(endpoint) {
        return this.request(endpoint, { method: 'GET' });
    }
    async post(endpoint, data) {
        return this.request(endpoint, {
            method: 'POST',
            body: data ? JSON.stringify(data) : undefined,
        });
    }
    async put(endpoint, data) {
        return this.request(endpoint, {
            method: 'PUT',
            body: data ? JSON.stringify(data) : undefined,
        });
    }
    async patch(endpoint, data) {
        return this.request(endpoint, {
            method: 'PATCH',
            body: data ? JSON.stringify(data) : undefined,
        });
    }
    async delete(endpoint) {
        return this.request(endpoint, { method: 'DELETE' });
    }
}
export const apiClient = new ApiClient();
