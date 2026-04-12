import { playersApi } from '../api/players.js';
import { toursApi } from '../api/tours.js';
import { matchesApi } from '../api/matches.js';
export class AdminPanel {
    constructor() {
        this.playerSelects = [];
        this.players = [];
        this.adminSection = document.getElementById('adminSection');
        this.adminToggleBtn = document.getElementById('adminToggleBtn');
        this.closeAdminBtn = document.getElementById('closeAdminBtn');
        this.tournamentSection = document.getElementById('tournamentSection');
        this.registerMatchForm = document.getElementById('registerMatchForm');
        this.createTourForm = document.getElementById('createTourForm');
        this.addPlayerForm = document.getElementById('addPlayerForm');
        this.tabButtons = document.querySelectorAll('.tab-button');
        this.tabContents = document.querySelectorAll('.tab-content');
        this.init();
    }
    async init() {
        this.setupEventListeners();
        this.setupTabs();
        await this.loadPlayers();
        this.setupDateTimeDefaults();
    }
    setupEventListeners() {
        this.adminToggleBtn.addEventListener('click', () => this.toggleAdminPanel());
        this.closeAdminBtn.addEventListener('click', () => this.toggleAdminPanel());
        this.registerMatchForm.addEventListener('submit', (e) => this.handleRegisterMatch(e));
        this.createTourForm.addEventListener('submit', (e) => this.handleCreateTour(e));
        this.addPlayerForm.addEventListener('submit', (e) => this.handleAddPlayer(e));
    }
    setupTabs() {
        this.tabButtons.forEach(button => {
            button.addEventListener('click', () => {
                const tabName = button.getAttribute('data-tab');
                this.switchTab(tabName);
            });
        });
    }
    switchTab(tabName) {
        this.tabButtons.forEach(btn => {
            btn.classList.toggle('active', btn.getAttribute('data-tab') === tabName);
        });
        this.tabContents.forEach(content => {
            content.classList.toggle('active', content.id === `${tabName}Tab`);
        });
    }
    setupDateTimeDefaults() {
        const now = new Date();
        const dateInput = document.getElementById('matchDate');
        const timeInput = document.getElementById('matchTime');
        dateInput.value = now.toISOString().split('T')[0];
        timeInput.value = now.toTimeString().slice(0, 5);
    }
    async loadPlayers() {
        try {
            this.players = await playersApi.getAll();
            this.populatePlayerSelects();
        }
        catch (error) {
            console.error('Failed to load players:', error);
            this.showNotification('Не удалось загрузить список игроков', 'error');
        }
    }
    populatePlayerSelects() {
        const selectIds = ['side1Player1', 'side1Player2', 'side2Player1', 'side2Player2'];
        selectIds.forEach(id => {
            const select = document.getElementById(id);
            if (select) {
                this.playerSelects.push(select);
                select.innerHTML = '<option value="">Выберите игрока</option>' +
                    this.players.map(player => `<option value="${player.id}">${this.escapeHtml(player.name)}</option>`).join('');
            }
        });
    }
    toggleAdminPanel() {
        this.adminSection.classList.toggle('hidden');
        this.tournamentSection.classList.toggle('hidden');
        if (!this.adminSection.classList.contains('hidden')) {
            this.loadPlayers();
        }
    }
    async handleRegisterMatch(event) {
        event.preventDefault();
        try {
            const matchData = this.collectMatchData();
            if (!this.validateMatchData(matchData)) {
                return;
            }
            await matchesApi.register(matchData);
            this.showNotification('Матч успешно зарегистрирован!', 'success');
            this.registerMatchForm.reset();
            this.setupDateTimeDefaults();
            const event_ = new CustomEvent('matchRegistered');
            window.dispatchEvent(event_);
        }
        catch (error) {
            console.error('Failed to register match:', error);
            this.showNotification('Не удалось зарегистрировать матч', 'error');
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
        if (players.some(id => !id)) {
            this.showNotification('Выберите всех игроков', 'error');
            return false;
        }
        if (data.side1.player1_id === data.side1.player2_id) {
            this.showNotification('Игроки на одной стороне должны быть разными', 'error');
            return false;
        }
        if (data.side2.player1_id === data.side2.player2_id) {
            this.showNotification('Игроки на одной стороне должны быть разными', 'error');
            return false;
        }
        const allPlayerIds = new Set(players);
        if (allPlayerIds.size !== 4) {
            this.showNotification('Один и тот же игрок не может быть на обеих сторонах', 'error');
            return false;
        }
        if (isNaN(data.side1.match_score) || data.side1.match_score < 0) {
            this.showNotification('Введите корректный счёт для стороны 1', 'error');
            return false;
        }
        if (isNaN(data.side2.match_score) || data.side2.match_score < 0) {
            this.showNotification('Введите корректный счёт для стороны 2', 'error');
            return false;
        }
        return true;
    }
    async handleCreateTour(event) {
        event.preventDefault();
        try {
            const tourName = document.getElementById('tourName').value.trim();
            if (!tourName) {
                this.showNotification('Введите название тура', 'error');
                return;
            }
            const tourData = {
                name: tourName,
                started_at: new Date().toISOString()
            };
            await toursApi.start(tourData);
            this.showNotification('Тур успешно создан!', 'success');
            this.createTourForm.reset();
            const event_ = new CustomEvent('tourCreated');
            window.dispatchEvent(event_);
        }
        catch (error) {
            console.error('Failed to create tour:', error);
            this.showNotification('Не удалось создать тур', 'error');
        }
    }
    async handleAddPlayer(event) {
        event.preventDefault();
        try {
            const playerName = document.getElementById('playerName').value.trim();
            if (!playerName) {
                this.showNotification('Введите имя игрока', 'error');
                return;
            }
            const playerData = {
                name: playerName,
                registered_at: new Date().toISOString()
            };
            await playersApi.create(playerData);
            this.showNotification('Игрок успешно добавлен!', 'success');
            this.addPlayerForm.reset();
            await this.loadPlayers();
        }
        catch (error) {
            console.error('Failed to add player:', error);
            this.showNotification('Не удалось добавить игрока', 'error');
        }
    }
    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 16px 24px;
            background: ${type === 'success' ? 'var(--success-color)' : type === 'error' ? 'var(--accent-color)' : 'var(--secondary-color)'};
            color: white;
            border-radius: 12px;
            box-shadow: var(--shadow-lg);
            z-index: 1000;
            animation: slideIn 0.3s ease;
            backdrop-filter: blur(10px);
            background: ${type === 'success' ? 'rgba(39, 174, 96, 0.9)' : type === 'error' ? 'rgba(231, 76, 60, 0.9)' : 'rgba(52, 152, 219, 0.9)'};
        `;
        document.body.appendChild(notification);
        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }

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
