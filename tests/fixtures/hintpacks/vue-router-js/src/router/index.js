import { createRouter, createWebHistory } from 'vue-router'
import SignupView from '../views/SignupView.vue'

const routes = [
  { path: '/signup', name: 'signup', component: SignupView },
]

export default createRouter({ history: createWebHistory(), routes })
