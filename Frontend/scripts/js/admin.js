import { playersApi } from './api/players.js';
import { toursApi } from './api/tours.js';
import { matchesApi } from './api/matches.js';
class AdminApp {
    constructor() {
        this.players = [];
        this.playerSelects = [];
        this.matchForm = document.getElementById('matchForm');
        this.tourForm = document.getElementById('tourForm');
        this.playerForm = document.getElementById('playerForm');
        this.playersList = document.getElementById('playersList');
        this.toastContainer = document.getElementById('toastContainer');
        this.tabs = document.querySelectorAll('.tab');
        this.tabContents = document.querySelectorAll('.tab-content');
        this.init();
    }
    async init() {
        this.setupTabs();
        this.setupEventListeners();
        this.setupDateTimeDefaults();
        await this.loadPlayers();
    }
    setupTabs() {
        this.tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                const tabName = tab.getAttribute('data-tab');
                this.switchTab(tabName);
            });
        });
    }
    switchTab(tabName) {
        this.tabs.forEach(tab => {
            tab.classList.toggle('tab--active', tab.getAttribute('data-tab') === tabName);
        });
        this.tabContents.forEach(content => {
            content.classList.toggle('tab-content--active', content.id === `tab-${tabName}`);
        });
    }
    setupEventListeners() {
        this.matchForm.addEventListener('submit', (e) => this.handleMatchSubmit(e));
        this.tourForm.addEventListener('submit', (e) => this.handleTourSubmit(e));
        this.playerForm.addEventListener('submit', (e) => this.handlePlayerSubmit(e));
    }
    setupDateTimeDefaults() {
        const now = new Date();
        const dateInput = document.getElementById('matchDate');
        const timeInput = document.getElementById('matchTime');
        const year = now.getFullYear();
        const month = String(now.getMonth() + 1).padStart(2, '0');
        const day = String(now.getDate()).padStart(2, '0');
        const hours = String(now.getHours()).padStart(2, '0');
        const minutes = String(now.getMinutes()).padStart(2, '0');
        dateInput.value = `${year}-${month}-${day}`;
        timeInput.value = `${hours}:${minutes}`;
    }
    async loadPlayers() {
        try {
            this.players = await playersApi.getAll();
            this.populatePlayerSelects();
            this.renderPlayersList();
        }
        catch (error) {
            console.error('Failed to load players:', error);
            this.showToast('Не удалось загрузить список игроков', 'error');
        }
    }
    populatePlayerSelects() {
        const selectIds = ['side1Player1', 'side1Player2', 'side2Player1', 'side2Player2'];
        this.playerSelects = [];
        selectIds.forEach(id => {
            const select = document.getElementById(id);
            if (select) {
                this.playerSelects.push(select);
                select.innerHTML = '<option value="">Выберите игрока</option>' +
                    this.players.map(player => `<option value="${player.id}">${this.escapeHtml(player.name)}</option>`).join('');
            }
        });
    }
    renderPlayersList() {
        if (this.players.length === 0) {
            this.playersList.innerHTML = '<div class="players-list__loading">Нет зарегистрированных игроков</div>';
            return;
        }
        const sortedPlayers = [...this.players].sort((a, b) => a.name.localeCompare(b.name));
        this.playersList.innerHTML = sortedPlayers.map((player, index) => `
            <div class="players-list__item">
                <span class="players-list__number">${index + 1}</span>
                <span class="players-list__name">${this.escapeHtml(player.name)}</span>
                <span class="players-list__date">${this.formatDate(player.registered_at)}</span>
            </div>
        `).join('');
    }
    async handleMatchSubmit(event) {
        event.preventDefault();
        try {
            const matchData = this.collectMatchData();
            if (!this.validateMatchData(matchData)) {
                return;
            }
            await matchesApi.register(matchData);
            this.showToast('Матч успешно зарегистрирован', 'success');
            this.matchForm.reset();
            this.setupDateTimeDefaults();
        }
        catch (error) {
            console.error('Failed to register match:', error);
            this.showToast('Не удалось зарегистрировать матч', 'error');
        }
    }
    collectMatchData() {
        const side1Player1 = parseInt(document.getElementById('side1Player1').value);
        const side1Player2 = parseInt(document.getElementById('side1Player2').value);
        const side1Score = parseInt(document.getElementById('side1Score').value);
        const side2Player1 = parseInt(document.getElementById('side2Player1').value);
        const side2Player2 = parseInt(document.getElementById('side2Player2').value);
        const side2Score = parseInt(document.getElementById('side2Score').value);
        const matchDate = document.getElementById('matchDate').value;
        const matchTime = document.getElementById('matchTime').value;
        const playedAt = new Date(`${matchDate}T${matchTime}`).toISOString();
        return {
            side1: {
                player1_id: side1Player1,
                player2_id: side1Player2,
                match_score: side1Score
            },
            side2: {
                player1_id: side2Player1,
                player2_id: side2Player2,
                match_score: side2Score
            },
            played_at: playedAt
        };
    }
    validateMatchData(data) {
        const players = [
            data.side1.player1_id, data.side1.player2_id,
            data.side2.player1_id, data.side2.player2_id
        ];
        if (players.some(id => !id || isNaN(id))) {
            this.showToast('Выберите всех игроков', 'error');
            return false;
        }
        if (data.side1.player1_id === data.side1.player2_id) {
            this.showToast('Игроки в первой паре должны быть разными', 'error');
            return false;
        }
        if (data.side2.player1_id === data.side2.player2_id) {
            this.showToast('Игроки во второй паре должны быть разными', 'error');
            return false;
        }
        const uniquePlayers = new Set(players);
        if (uniquePlayers.size !== 4) {
            this.showToast('Один игрок не может быть в обеих парах', 'error');
            return false;
        }
        if (isNaN(data.side1.match_score) || data.side1.match_score < 0) {
            this.showToast('Введите корректный счёт для первой пары', 'error');
            return false;
        }
        if (isNaN(data.side2.match_score) || data.side2.match_score < 0) {
            this.showToast('Введите корректный счёт для второй пары', 'error');
            return false;
        }
        return true;
    }
    async handleTourSubmit(event) {
        event.preventDefault();
        try {
            const tourName = document.getElementById('tourName').value.trim();
            if (!tourName) {
                this.showToast('Введите название тура', 'error');
                return;
            }
            const tourData = {
                name: tourName,
                started_at: new Date().toISOString()
            };
            await toursApi.start(tourData);
            this.showToast('Тур успешно создан', 'success');
            this.tourForm.reset();
        }
        catch (error) {
            console.error('Failed to create tour:', error);
            this.showToast('Не удалось создать тур', 'error');
        }
    }
    async handlePlayerSubmit(event) {
        event.preventDefault();
        try {
            const playerName = document.getElementById('playerName').value.trim();
            if (!playerName) {
                this.showToast('Введите имя игрока', 'error');
                return;
            }
            const playerData = {
                name: playerName,
                registered_at: new Date().toISOString()
            };
            await playersApi.create(playerData);
            this.showToast('Игрок успешно добавлен', 'success');
            this.playerForm.reset();
            await this.loadPlayers();
        }
        catch (error) {
            console.error('Failed to add player:', error);
            this.showToast('Не удалось добавить игрока', 'error');
        }
    }
    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast toast--${type}`;
        toast.textContent = message;
        this.toastContainer.appendChild(toast);
        setTimeout(() => {
            toast.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }
    formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString('ru-RU');
    }
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}
document.addEventListener('DOMContentLoaded', () => {
    new AdminApp();
});
const style = document.createElement('style');
style.textContent = `
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);
