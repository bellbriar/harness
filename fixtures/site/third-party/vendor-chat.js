setTimeout(function () {
  var c = document.createElement('div');
  c.id = 'intercom-container';
  c.innerHTML = '<button><svg></svg></button><img src="avatar.png">' +
                '<div tabindex="3">Chat</div>';
  document.body.appendChild(c);
  setInterval(function () { fetch('/beacon').catch(function () {}); }, 300);
}, 40);
