document.addEventListener('DOMContentLoaded', function() {
    // Sidebar toggle functionality
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const appContainer = document.querySelector('.app-container');
    
    sidebarToggle.addEventListener('click', function() {
        sidebar.classList.toggle('collapsed');
        appContainer.classList.toggle('sidebar-collapsed');
    });
    
    // Mobile chat sidebar toggle
    const chatHeader = document.querySelector('.chat-header');
    const rightSidebar = document.querySelector('.right-sidebar');
    
    if (chatHeader && rightSidebar && window.innerWidth <= 768) {
        chatHeader.addEventListener('click', function() {
            rightSidebar.classList.toggle('expanded');
        });
    }
    
    // Search form submission
    const searchForm = document.getElementById('search-form');
    const searchInput = document.getElementById('search-input');
    const resultsGrid = document.getElementById('results-grid');
    const loadingSpinner = document.getElementById('loading-spinner');
    const resultsSection = document.getElementById('results-section');
    
    // Check if we're on the results page and should show results
    if (window.location.pathname === '/results' && resultsGrid) {
        // The results are already rendered by the server
        resultsSection.style.display = 'block';
    }
    
    if (searchForm) {
        // Make sure the form submits when pressing Enter
        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                const query = this.value.trim();
                if (query) {
                    searchForm.submit();
                } else {
                    e.preventDefault();
                }
            }
        });
        
        searchForm.addEventListener('submit', function(e) {
            const query = searchInput.value.trim();
            if (!query) {
                e.preventDefault();
                return;
            }
        });
    }
    
    // Autocomplete functionality
    const autocompleteResults = document.getElementById('autocomplete-results');
    
    // Sample topics for autocomplete
    const sampleTopics = [
        'Machine Learning', 'Artificial Intelligence', 'Deep Learning',
        'Natural Language Processing', 'Computer Vision', 'Robotics',
        'Quantum Computing', 'Blockchain', 'Cybersecurity',
        'Bioinformatics', 'Climate Science', 'Neuroscience'
    ];
    
    if (searchInput && autocompleteResults) {
        searchInput.addEventListener('input', function() {
            const query = this.value.trim().toLowerCase();
            
            if (query.length < 2) {
                autocompleteResults.style.display = 'none';
                return;
            }
            
            const matchedTopics = sampleTopics.filter(topic => 
                topic.toLowerCase().includes(query)
            );
            
            if (matchedTopics.length > 0) {
                autocompleteResults.innerHTML = '';
                matchedTopics.forEach(topic => {
                    const item = document.createElement('div');
                    item.className = 'autocomplete-item';
                    item.textContent = topic;
                    item.addEventListener('click', function() {
                        searchInput.value = topic;
                        autocompleteResults.style.display = 'none';
                        searchForm.submit();
                    });
                    autocompleteResults.appendChild(item);
                });
                autocompleteResults.style.display = 'block';
            } else {
                autocompleteResults.style.display = 'none';
            }
        });
    }
    
    // Hide autocomplete when clicking outside
    document.addEventListener('click', function(e) {
        if (searchInput && autocompleteResults && 
            !searchInput.contains(e.target) && 
            !autocompleteResults.contains(e.target)) {
            autocompleteResults.style.display = 'none';
        }
    });
    
    // Scroll to bottom of chat messages
    
    
    // Function to display search results
    function displayResults(data) {
        if (!data || data.length === 0) {
            resultsGrid.innerHTML = `
                <div class="no-results">
                    <p>No results found. Please try a different search term.</p>
                </div>
            `;
            return;
        }
        
        resultsGrid.innerHTML = '';
        const template = document.getElementById('result-card-template');
        
        data.forEach(paper => {
            const card = document.importNode(template.content, true);
            
            // Fill in the card with paper data
            card.querySelector('.paper-title').textContent = paper.title;
            card.querySelector('.paper-authors').textContent = paper.authors || 'Unknown Authors';
            card.querySelector('.paper-date').textContent = paper.published || 'Unknown Date';
            card.querySelector('.summary-content').textContent = paper.summary;
            
            if (paper.url) {
                const viewOriginal = card.querySelector('.view-original');
                viewOriginal.href = paper.url;
            }
            
            // Add event listeners for action buttons
            const saveButton = card.querySelector('.save-button');
            saveButton.addEventListener('click', function() {
                this.classList.toggle('active');
                if (this.classList.contains('active')) {
                    this.innerHTML = '<i class="fas fa-bookmark"></i>';
                    this.style.color = '#34a853';
                } else {
                    this.innerHTML = '<i class="far fa-bookmark"></i>';
                    this.style.color = '';
                }
            });
            
            const downloadButton = card.querySelector('.download-button');
            downloadButton.addEventListener('click', function() {
                // Download functionality would go here
                alert('Download functionality will be implemented soon!');
            });
            
            const shareButton = card.querySelector('.share-button');
            shareButton.addEventListener('click', function() {
                // Share functionality would go here
                alert('Share functionality will be implemented soon!');
            });
            
            resultsGrid.appendChild(card);
        });
    }

    // Chat form handling
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const chatMessages = document.getElementById('chat-messages');
    if (chatMessages) {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    if (chatForm && chatMessages) {
        chatForm.addEventListener('submit', function(e) {
            e.preventDefault(); // Prevent the form from submitting normally
            
            const message = chatInput.value.trim();
            if (!message) return;
            
            // Add user message to chat
            addMessageToChat('user', message);
            
            // Clear input
            chatInput.value = '';
            
            // Show loading indicator
            const loadingMessage = addMessageToChat('assistant', '<div class="typing-indicator"><span></span><span></span><span></span></div>');
            
            // Send request to server
            fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: message })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                // Remove loading indicator
                loadingMessage.remove();
                
                // Add assistant response to chat
                if (data.response) {
                    addMessageToChat('assistant', data.response);
                } else if (data.error) {
                    addMessageToChat('assistant', 'Error: ' + data.error);
                } else {
                    addMessageToChat('assistant', 'Received an empty response from the server.');
                }
                
                // Scroll to bottom of chat
                chatMessages.scrollTop = chatMessages.scrollHeight;
            })
            .catch(error => {
                // Remove loading indicator
                loadingMessage.remove();
                
                // Add error message
                addMessageToChat('assistant', 'Sorry, there was an error processing your request. Please try again.');
                console.error('Error:', error);
            });
        });
        
        // Function to add a message to the chat
        function addMessageToChat(role, content) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `chat-message ${role}-message`;
            
            const contentDiv = document.createElement('div');
            contentDiv.className = 'message-content';
            contentDiv.innerHTML = content;
            
            messageDiv.appendChild(contentDiv);
            chatMessages.appendChild(messageDiv);
            
            // Scroll to bottom of chat
            chatMessages.scrollTop = chatMessages.scrollHeight;
            
            return messageDiv;
        }
    }
}); 