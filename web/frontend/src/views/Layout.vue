<template>
  <el-container class="layout-container">
    <!-- 移动端遮罩层 -->
    <transition name="fade">
      <div v-if="isMobile && sidebarVisible" class="sidebar-overlay" @click="closeSidebar"></div>
    </transition>
    
    <!-- 侧边栏 -->
    <el-aside 
      :class="['sidebar', { 'sidebar--mobile': isMobile, 'sidebar--open': sidebarVisible && isMobile }]"
      :style="{ width: sidebarWidth }"
    >
      <div class="sidebar__logo">
        <span v-if="!isCollapsed || isMobile">评分系统</span>
        <span v-else class="sidebar__logo--short">DS</span>
      </div>
      
      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapsed && !isMobile"
        :collapse-transition="false"
        :router="true"
        class="sidebar__menu"
        @select="handleMenuSelect"
      >
        <el-menu-item index="/dashboard">
          <el-icon><HomeFilled /></el-icon>
          <template #title>首页</template>
        </el-menu-item>
        
        <el-menu-item index="/competitions">
          <el-icon><Trophy /></el-icon>
          <template #title>赛事管理</template>
        </el-menu-item>
        
        <el-menu-item v-if="userStore.role === 'admin'" index="/users">
          <el-icon><User /></el-icon>
          <template #title>用户管理</template>
        </el-menu-item>
        
        <el-menu-item v-if="userStore.role === 'admin'" index="/logs">
          <el-icon><Document /></el-icon>
          <template #title>操作日志</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container class="main-container">
      <!-- 顶部导航 -->
      <el-header class="header">
        <div class="header__left">
          <el-button 
            :icon="sidebarVisible ? 'Close' : 'Menu'" 
            text 
            class="header__toggle"
            @click="toggleSidebar"
          />
          <h1 class="header__title">{{ pageTitle }}</h1>
        </div>
        
        <div class="header__right">
          <el-dropdown @command="handleCommand">
            <span class="header__user">
              <el-icon><Avatar /></el-icon>
              <span class="header__username">{{ userStore.userName || '用户' }}</span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">
                  <el-icon><SwitchButton /></el-icon>
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- 主内容区 -->
      <el-main class="main">
        <router-view v-slot="{ Component }">
          <transition name="fade-slide" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/store/user'
import {
  HomeFilled,
  Trophy,
  User,
  Document,
  Avatar,
  ArrowDown,
  SwitchButton
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

// 响应式状态
const windowWidth = ref(window.innerWidth)
const isCollapsed = ref(false)

// 移动端侧边栏状态
const sidebarVisible = ref(false)

// 是否移动端
const isMobile = computed(() => windowWidth.value <= 768)

// 侧边栏宽度
const sidebarWidth = computed(() => {
  if (isMobile.value) {
    return sidebarVisible.value ? '280px' : '0px'
  }
  return isCollapsed.value ? '64px' : '220px'
})

// 当前激活的菜单
const activeMenu = computed(() => route.path)

// 页面标题
const pageTitle = computed(() => {
  const titles: Record<string, string> = {
    '/dashboard': '首页',
    '/competitions': '赛事管理',
    '/users': '用户管理',
    '/logs': '操作日志'
  }
  return titles[route.path] || '评分系统'
})

// 切换侧边栏
const toggleSidebar = () => {
  if (isMobile.value) {
    sidebarVisible.value = !sidebarVisible.value
  } else {
    isCollapsed.value = !isCollapsed.value
  }
}

// 关闭侧边栏
const closeSidebar = () => {
  sidebarVisible.value = false
}

// 菜单选择
const handleMenuSelect = (index: string) => {
  if (isMobile.value) {
    closeSidebar()
  }
  router.push(index)
}

// 处理下拉命令
const handleCommand = (command: string) => {
  if (command === 'logout') {
    userStore.logout()
    ElMessage.success('已退出登录')
    router.push('/login')
  }
}

// 处理窗口大小变化
const handleResize = () => {
  windowWidth.value = window.innerWidth
  
  // 当窗口变大时关闭移动端侧边栏
  if (windowWidth.value > 768) {
    sidebarVisible.value = false
  }
}

// 监听路由变化
watch(() => route.path, () => {
  if (isMobile.value) {
    closeSidebar()
  }
})

// 生命周期
onMounted(() => {
  window.addEventListener('resize', handleResize)
  handleResize()
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})
</script>

<style lang="scss" scoped>
.layout-container {
  height: 100vh;
  overflow: hidden;
}

// 遮罩层
.sidebar-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 999;
  backdrop-filter: blur(2px);
}

// 侧边栏
.sidebar {
  background: linear-gradient(180deg, #304156 0%, #2c3e50 100%);
  color: white;
  display: flex;
  flex-direction: column;
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.15);

  &--mobile {
    position: fixed;
    top: 0;
    left: 0;
    height: 100vh;
    z-index: 1000;
    box-shadow: 4px 0 12px rgba(0, 0, 0, 0.2);
  }

  &__logo {
    height: 60px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, #409eff 0%, #66b1ff 100%);
    font-size: 18px;
    font-weight: bold;
    color: white;
    letter-spacing: 2px;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);

    &--short {
      font-size: 20px;
    }
  }

  &__menu {
    flex: 1;
    border-right: none;
    background: transparent;
    overflow-y: auto;
    overflow-x: hidden;

    :deep(.el-menu-item) {
      color: rgba(255, 255, 255, 0.85);
      height: 56px;
      line-height: 56px;
      margin: 4px 8px;
      border-radius: 8px;
      transition: all 0.3s;

      &:hover {
        background: rgba(255, 255, 255, 0.1);
        color: white;
      }

      &.is-active {
        background: linear-gradient(135deg, #409eff 0%, #66b1ff 100%);
        color: white;
        font-weight: 600;
        box-shadow: 0 2px 8px rgba(64, 158, 255, 0.4);
      }

      .el-icon {
        font-size: 18px;
        margin-right: 12px;
      }
    }

    :deep(.el-menu--collapse) {
      .el-menu-item {
        padding: 0 20px;
        
        .el-icon {
          margin: 0;
        }
      }
    }
  }
}

// 主容器
.main-container {
  display: flex;
  flex-direction: column;
  background: #f5f7fa;
  min-width: 0;
}

// 顶部导航
.header {
  background: white;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  z-index: 100;
  height: 60px;

  &__left {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  &__toggle {
    font-size: 24px;
    width: 40px;
    height: 40px;
    border-radius: 8px;
    transition: all 0.3s;

    &:hover {
      background: #f5f7fa;
    }
  }

  &__title {
    font-size: 18px;
    font-weight: 600;
    color: #303133;
    margin: 0;
  }

  &__right {
    display: flex;
    align-items: center;
  }

  &__user {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.3s;

    &:hover {
      background: #f5f7fa;
    }

    .el-icon {
      color: #909399;
    }
  }

  &__username {
    font-size: 14px;
    color: #606266;
    font-weight: 500;
  }
}

// 主内容区
.main {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
  background: #f5f7fa;
}

// 响应式布局
@media (max-width: 768px) {
  .sidebar {
    transform: translateX(-100%);
    transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);

    &--open {
      transform: translateX(0);
    }
  }

  .header {
    padding: 0 12px;

    &__title {
      font-size: 16px;
    }

    &__username {
      display: none;
    }
  }

  .main {
    padding: 12px;
  }
}

// 过渡动画
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.3s;
}

.fade-slide-enter-from {
  opacity: 0;
  transform: translateX(20px);
}

.fade-slide-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}
</style>
